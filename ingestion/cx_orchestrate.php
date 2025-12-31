<?php

declare(strict_types=1);

/**
 * CX ingestion orchestrator.
 *
 * Responsibilities:
 *  1) Run the ingestion request (php_cx_request.php)
 *  2) Read the generated manifest.json
 *  3) Write a clean orchestration event payload (event.json)
 *  4) Optionally POST the event to a webhook (Power Automate / etc)
 *
 * Usage:
 *   php ingestion/cx_orchestrate.php 'https://...'
 *
 * Env:
 *   CX_ORCH_WEBHOOK_ENABLED=true|false (default false)
 *   CX_ORCH_WEBHOOK_URL=<url>
 *   CX_ORCH_WEBHOOK_TIMEOUT_SECONDS=15
 *   CX_ORCH_INCLUDE_MANIFEST=true|false (default true)
 *
 * Fan-out routing (optional):
 *   CX_ORCH_ROUTE_ENABLED=true|false (default false)
 *   CX_ORCH_TARGETS_JSON=[{"name":"power","url":"https://...","timeout_seconds":15,"headers":{"x-api-key":"..."},"include_manifest":true,"include_rows":false,"max_rows":200,"max_ndjson_bytes":500000}] 
 *     - headers are treated as secrets (not printed)
 *     - include_rows sends parsed rows (capped)
 *     - max_ndjson_bytes includes ndjson text (capped) when rows.ndjson exists
 */

function orch_bool(string $v, bool $default = false): bool
{
    $v = trim($v);
    if ($v === '') {
        return $default;
    }
    return in_array(strtolower($v), ['1', 'true', 'yes', 'on'], true);
}

/**
 * @param array<string, mixed> $payload
 * @param array<string, string> $headers
 */
function orch_post_json_with_headers(string $url, array $payload, int $timeoutSeconds, array $headers = []): array
{
    $ch = curl_init($url);
    if ($ch === false) {
        return ['ok' => false, 'error' => 'curl_init_failed'];
    }

    $body = json_encode($payload, JSON_UNESCAPED_SLASHES);
    if (!is_string($body)) {
        $body = '{}';
    }

    $hdrs = [
        'Content-Type: application/json',
        'Accept: application/json',
        'User-Agent: cxflow-orchestrator/1.0',
    ];
    foreach ($headers as $k => $v) {
        $k = trim((string) $k);
        if ($k === '') {
            continue;
        }
        $hdrs[] = $k . ': ' . (string) $v;
    }

    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 2,
        CURLOPT_CONNECTTIMEOUT => min(10, max(1, $timeoutSeconds)),
        CURLOPT_TIMEOUT => max(1, $timeoutSeconds),
        CURLOPT_HTTPHEADER => $hdrs,
        CURLOPT_POSTFIELDS => $body,
    ]);

    $resp = curl_exec($ch);
    $errno = curl_errno($ch);
    $err = curl_error($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($resp === false) {
        return ['ok' => false, 'http_code' => $code, 'curl_errno' => $errno, 'message' => $err];
    }

    return ['ok' => $code >= 200 && $code < 300, 'http_code' => $code];
}

/**
 * @return array<int, array<string, mixed>>
 */
function orch_read_ndjson_rows(string $path, int $maxRows = 0): array
{
    if (!is_file($path)) {
        return [];
    }

    $fh = fopen($path, 'rb');
    if ($fh === false) {
        return [];
    }

    $rows = [];
    try {
        while (!feof($fh)) {
            $line = fgets($fh);
            if ($line === false) {
                break;
            }
            $line = trim($line);
            if ($line === '') {
                continue;
            }
            /** @var mixed $json */
            $json = json_decode($line, true);
            if (is_array($json)) {
                /** @var array<string, mixed> $json */
                $rows[] = $json;
            }
            if ($maxRows > 0 && count($rows) >= $maxRows) {
                break;
            }
        }
    } finally {
        fclose($fh);
    }

    return $rows;
}

function orch_read_text_cap(string $path, int $maxBytes): ?string
{
    if (!is_file($path)) {
        return null;
    }
    if ($maxBytes <= 0) {
        return (string) file_get_contents($path);
    }
    return (string) file_get_contents($path, false, null, 0, $maxBytes);
}

function orch_run_supabase_upload(?string $runDir): ?array
{
    if (!is_string($runDir) || $runDir === '' || !is_dir($runDir)) {
        return null;
    }

    $enabled = orch_bool((string) (getenv('SUPABASE_UPLOAD_ENABLED') ?: 'false'), false);
    if (!$enabled) {
        return null;
    }

    $php = PHP_BINARY;
    $script = __DIR__ . '/supabase_upload.php';
    if (!is_file($script)) {
        return ['ok' => false, 'error' => 'missing_uploader_script'];
    }

    $cmd = escapeshellarg($php) . ' ' . escapeshellarg($script) . ' ' . escapeshellarg($runDir);
    $out = [];
    $rc = 0;
    exec($cmd, $out, $rc);

    $stdout = implode("\n", $out);
    /** @var mixed $json */
    $json = json_decode($stdout, true);
    $res = is_array($json) ? $json : ['ok' => false, 'error' => 'invalid_uploader_output'];
    $res['exit_code'] = $rc;

    file_put_contents(
        rtrim($runDir, '/') . '/supabase.upload.result.json',
        json_encode($res, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n"
    );

    return $res;
}

/**
 * @return array<int, array{name:string,url:string,timeout_seconds:int,headers:array<string,string>,include_manifest:bool,include_rows:bool,max_rows:int,max_ndjson_bytes:int}>
 */
function orch_parse_targets(): array
{
    $raw = trim((string) (getenv('CX_ORCH_TARGETS_JSON') ?: ''));
    if ($raw === '') {
        return [];
    }

    /** @var mixed $json */
    $json = json_decode($raw, true);
    if (!is_array($json)) {
        return [];
    }

    $targets = [];
    foreach ($json as $t) {
        if (!is_array($t)) {
            continue;
        }

        $name = is_string($t['name'] ?? null) ? trim((string) $t['name']) : '';
        $url = is_string($t['url'] ?? null) ? trim((string) $t['url']) : '';
        if ($name === '' || $url === '') {
            continue;
        }

        $timeout = is_int($t['timeout_seconds'] ?? null) ? (int) $t['timeout_seconds'] : (int) (getenv('CX_ORCH_WEBHOOK_TIMEOUT_SECONDS') ?: 15);

        $headers = [];
        if (is_array($t['headers'] ?? null)) {
            foreach ((array) $t['headers'] as $hk => $hv) {
                if (is_string($hk) && is_string($hv)) {
                    $headers[$hk] = $hv;
                }
            }
        }

        $targets[] = [
            'name' => $name,
            'url' => $url,
            'timeout_seconds' => max(1, (int) $timeout),
            'headers' => $headers,
            'include_manifest' => isset($t['include_manifest']) ? (bool) $t['include_manifest'] : true,
            'include_rows' => isset($t['include_rows']) ? (bool) $t['include_rows'] : false,
            'max_rows' => isset($t['max_rows']) ? max(0, (int) $t['max_rows']) : 200,
            'max_ndjson_bytes' => isset($t['max_ndjson_bytes']) ? max(0, (int) $t['max_ndjson_bytes']) : 500000,
        ];
    }

    return $targets;
}

/** @return array<string, mixed>|null */
function orch_read_json(string $path): ?array
{
    if (!is_file($path)) {
        return null;
    }
    $raw = (string) file_get_contents($path);
    /** @var mixed $json */
    $json = json_decode($raw, true);
    return is_array($json) ? $json : null;
}

/**
 * @param array<string,mixed> $payload
 */
function orch_post_json(string $url, array $payload, int $timeoutSeconds): array
{
    $ch = curl_init($url);
    if ($ch === false) {
        return ['ok' => false, 'error' => 'curl_init_failed'];
    }

    $body = json_encode($payload, JSON_UNESCAPED_SLASHES);
    if (!is_string($body)) {
        $body = '{}';
    }

    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 2,
        CURLOPT_CONNECTTIMEOUT => min(10, max(1, $timeoutSeconds)),
        CURLOPT_TIMEOUT => max(1, $timeoutSeconds),
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/json',
            'Accept: application/json',
            'User-Agent: cxflow-orchestrator/1.0',
        ],
        CURLOPT_POSTFIELDS => $body,
    ]);

    $resp = curl_exec($ch);
    $errno = curl_errno($ch);
    $err = curl_error($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($resp === false) {
        return ['ok' => false, 'http_code' => $code, 'curl_errno' => $errno, 'message' => $err];
    }

    return ['ok' => $code >= 200 && $code < 300, 'http_code' => $code];
}

$url = trim((string) ($argv[1] ?? ''));
if ($url === '') {
    fwrite(STDERR, "Missing URL argument.\n");
    fwrite(STDERR, "Usage: php ingestion/cx_orchestrate.php 'https://...'\n");
    exit(2);
}

$php = PHP_BINARY;
$script = __DIR__ . '/php_cx_request.php';
if (!is_file($script)) {
    fwrite(STDERR, "Missing ingestion/php_cx_request.php\n");
    exit(2);
}

// Run ingestion as a subprocess so we can keep this file small and stable.
$cmd = escapeshellarg($php) . ' ' . escapeshellarg($script) . ' ' . escapeshellarg($url);
$output = [];
$rc = 0;
exec($cmd, $output, $rc);

$stdout = implode("\n", $output);
/** @var mixed $summary */
$summary = json_decode($stdout, true);

$runDir = null;
$manifestPath = null;
$runId = null;
$ok = false;

if (is_array($summary)) {
    $runDir = is_string($summary['run_dir'] ?? null) ? (string) $summary['run_dir'] : null;
    $manifestPath = is_string($summary['manifest'] ?? null) ? (string) $summary['manifest'] : null;
    $runId = is_string($summary['run_id'] ?? null) ? (string) $summary['run_id'] : null;
    $ok = ($summary['ok'] ?? false) === true;
}

$manifest = is_string($manifestPath) ? orch_read_json($manifestPath) : null;

$event = [
    'event' => $ok ? 'cx.ingestion.completed' : 'cx.ingestion.failed',
    'occurred_at' => gmdate('c'),
    'run_id' => $runId,
    'ok' => $ok,
    'ingestion' => [
        'run_dir' => $runDir,
        'http_code' => is_array($manifest) ? ($manifest['response']['http_code'] ?? null) : null,
        'content_type' => is_array($manifest) ? ($manifest['response']['content_type'] ?? null) : null,
        'rows_ndjson' => is_array($manifest) ? ($manifest['artifacts']['rows_ndjson'] ?? null) : null,
        'rows_csv' => is_array($manifest) ? ($manifest['artifacts']['rows_csv'] ?? null) : null,
    ],
];

$includeManifest = orch_bool((string) (getenv('CX_ORCH_INCLUDE_MANIFEST') ?: 'true'), true);
if ($includeManifest) {
    $event['manifest'] = $manifest;
}

$eventPath = null;
if (is_string($runDir) && $runDir !== '' && is_dir($runDir)) {
    $eventPath = rtrim($runDir, '/') . '/event.json';
    file_put_contents($eventPath, json_encode($event, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
}

// Optional webhook.
$webhookEnabled = orch_bool((string) (getenv('CX_ORCH_WEBHOOK_ENABLED') ?: 'false'), false);
$webhookUrl = trim((string) (getenv('CX_ORCH_WEBHOOK_URL') ?: ''));
$timeout = (int) (getenv('CX_ORCH_WEBHOOK_TIMEOUT_SECONDS') ?: 15);

$webhookResult = null;
if ($webhookEnabled && $webhookUrl !== '') {
    // URL is treated as secret; do not log.
    $webhookResult = orch_post_json($webhookUrl, $event, max(1, $timeout));

    if ($eventPath !== null) {
        file_put_contents(
            rtrim((string) $runDir, '/') . '/webhook.result.json',
            json_encode($webhookResult, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n"
        );
    }
}

// Optional fan-out routing to downstream systems.
$routeEnabled = orch_bool((string) (getenv('CX_ORCH_ROUTE_ENABLED') ?: 'false'), false);
$routeResults = [];
if ($routeEnabled) {
    $targets = orch_parse_targets();

    // Backward-compatible single target via CX_ORCH_WEBHOOK_* (if targets_json omitted).
    if (count($targets) === 0) {
        $singleUrl = trim((string) (getenv('CX_ORCH_WEBHOOK_URL') ?: ''));
        if ($singleUrl !== '') {
            $targets[] = [
                'name' => 'default',
                'url' => $singleUrl,
                'timeout_seconds' => max(1, (int) (getenv('CX_ORCH_WEBHOOK_TIMEOUT_SECONDS') ?: 15)),
                'headers' => [],
                'include_manifest' => true,
                'include_rows' => false,
                'max_rows' => 200,
                'max_ndjson_bytes' => 500000,
            ];
        }
    }

    $rowsPath = is_array($manifest) ? ($manifest['artifacts']['rows_ndjson'] ?? null) : null;
    $rowsPath = is_string($rowsPath) ? $rowsPath : null;

    foreach ($targets as $t) {
        $name = (string) $t['name'];
        $url2 = (string) $t['url'];
        $timeout2 = (int) $t['timeout_seconds'];
        /** @var array<string,string> $hdrs */
        $hdrs = (array) $t['headers'];

        $payload = [
            'event' => (string) $event['event'],
            'occurred_at' => (string) $event['occurred_at'],
            'run_id' => $runId,
            'ok' => $ok,
            'ingestion' => $event['ingestion'],
        ];

        if ((bool) $t['include_manifest']) {
            $payload['manifest'] = $manifest;
        }

        // Optional rows
        if ((bool) $t['include_rows'] && is_string($rowsPath) && is_file($rowsPath)) {
            $payload['rows'] = orch_read_ndjson_rows($rowsPath, (int) $t['max_rows']);
        }

        // Optional ndjson text (capped)
        if (is_string($rowsPath) && is_file($rowsPath)) {
            $nd = orch_read_text_cap($rowsPath, (int) $t['max_ndjson_bytes']);
            if (is_string($nd) && $nd !== '') {
                $payload['rows_ndjson_text'] = $nd;
            }
        }

        // Never log URL/headers; just store status.
        $res = orch_post_json_with_headers($url2, $payload, $timeout2, $hdrs);
        $routeResults[$name] = $res;

        if ($runDir !== null) {
            $safe = preg_replace('#[^A-Za-z0-9._-]+#', '_', $name) ?: 'target';
            file_put_contents(
                rtrim((string) $runDir, '/') . '/route.' . $safe . '.result.json',
                json_encode($res, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n"
            );
        }
    }
}

// Optional Supabase Storage upload (uploads run artifacts + extracted files).
$supabaseUpload = orch_run_supabase_upload($runDir);

// Print clean summary to stdout.
echo json_encode([
    'ok' => $ok,
    'run_id' => $runId,
    'run_dir' => $runDir,
    'manifest' => $manifestPath,
    'event' => $eventPath,
    'webhook' => $webhookResult,
    'routes' => $routeResults,
    'supabase_upload' => $supabaseUpload,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";

exit($ok ? 0 : ($rc !== 0 ? $rc : 1));
