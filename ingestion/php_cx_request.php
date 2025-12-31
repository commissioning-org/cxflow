<?php

declare(strict_types=1);

/**
 * Simple ingestion GET requester.
 *
 * Sends a GET request to a Power Automate HTTP trigger (or any URL) with:
 *   request_type: php_cx_request
 *
 * IMPORTANT: Do not hardcode signed Power Automate URLs in git.
 * Provide the URL via CLI (Option B).
 *
 * Usage:
 *   php ingestion/php_cx_request.php 'https://...'
 */

/**
 * NOTE ABOUT SECRETS
 * ------------------
 * Many Power Automate trigger URLs contain a signed `sig=...` query parameter.
 * Treat the full URL as a secret. This script:
 *  - never prints the full URL
 *  - stores only a redacted URL in output files
 */

/**
 * @return array{url:string, out_dir:string, decode_files:bool, max_decode_bytes:int}
 */
function cx_parse_args(array $argv): array
{
    $help = in_array('-h', $argv, true) || in_array('--help', $argv, true);
    if ($help) {
        fwrite(STDOUT, "Usage: php ingestion/php_cx_request.php <url>\n\n");
        fwrite(STDOUT, "Environment options:\n");
        fwrite(STDOUT, "  CX_INGESTION_OUT_DIR                Output base directory (default: ingestion/runs)\n");
        fwrite(STDOUT, "  CX_INGESTION_TIMEOUT_SECONDS        Total request timeout (default: 30)\n");
        fwrite(STDOUT, "  CX_INGESTION_CONNECT_TIMEOUT_SECONDS Connect timeout (default: 10)\n");
        fwrite(STDOUT, "  CX_INGESTION_MAX_BODY_BYTES         Cap stored body bytes (0 = unlimited; default: 0)\n");
        fwrite(STDOUT, "  CX_INGESTION_MAX_PARSE_BYTES        Cap parsed bytes for JSON/CSV/NDJSON (default: 25000000)\n");
        fwrite(STDOUT, "  CX_INGESTION_PARSE_ON_FAILURE       Parse body even for non-2xx (default: true)\n");
        fwrite(STDOUT, "  CX_INGESTION_DECODE_GZIP            If response is gzip, decode for parsing (default: true)\n");
        fwrite(STDOUT, "  CX_INGESTION_MAX_ROWS               Max rows to extract/write (default: 5000)\n");
        fwrite(STDOUT, "  CX_INGESTION_HEADERS_JSON           Extra request headers as JSON object (values are NOT logged)\n");
        fwrite(STDOUT, "\n");
        exit(0);
    }

    $url = trim((string) ($argv[1] ?? ''));

    // Defaults
    $outDir = (string) (getenv('CX_INGESTION_OUT_DIR') ?: (dirname(__FILE__) . '/runs'));
    $decodeFiles = (string) (getenv('CX_INGESTION_DECODE_FILES') ?: 'true');
    $maxDecodeBytes = (int) (getenv('CX_INGESTION_MAX_DECODE_BYTES') ?: 20_000_000); // 20MB

    $timeoutSeconds = (int) (getenv('CX_INGESTION_TIMEOUT_SECONDS') ?: 30);
    $connectTimeoutSeconds = (int) (getenv('CX_INGESTION_CONNECT_TIMEOUT_SECONDS') ?: 10);
    $maxBodyBytes = (int) (getenv('CX_INGESTION_MAX_BODY_BYTES') ?: 0);
    $maxParseBytes = (int) (getenv('CX_INGESTION_MAX_PARSE_BYTES') ?: 25_000_000); // 25MB
    $parseOnFailure = (string) (getenv('CX_INGESTION_PARSE_ON_FAILURE') ?: 'true');
    $decodeGzip = (string) (getenv('CX_INGESTION_DECODE_GZIP') ?: 'true');
    $maxRows = (int) (getenv('CX_INGESTION_MAX_ROWS') ?: 5000);
    $headersJson = (string) (getenv('CX_INGESTION_HEADERS_JSON') ?: '');

    return [
        'url' => $url,
        'out_dir' => $outDir,
        'decode_files' => in_array(strtolower($decodeFiles), ['1', 'true', 'yes', 'on'], true),
        'max_decode_bytes' => max(0, $maxDecodeBytes),
        'timeout_seconds' => max(1, $timeoutSeconds),
        'connect_timeout_seconds' => max(1, $connectTimeoutSeconds),
        'max_body_bytes' => max(0, $maxBodyBytes),
        'max_parse_bytes' => max(0, $maxParseBytes),
        'parse_on_failure' => in_array(strtolower($parseOnFailure), ['1', 'true', 'yes', 'on'], true),
        'decode_gzip' => in_array(strtolower($decodeGzip), ['1', 'true', 'yes', 'on'], true),
        'max_rows' => max(0, $maxRows),
        'headers_json' => $headersJson,
    ];
}

function cx_redact_url(string $url): string
{
    // Replace query string with a redacted marker.
    $redacted = preg_replace('#(\?.*)$#', '?<redacted>', $url);
    return is_string($redacted) && $redacted !== '' ? $redacted : '<redacted>';
}

/** @return string */
function cx_mkdir_p(string $path): string
{
    if (!is_dir($path)) {
        mkdir($path, 0775, true);
    }
    return $path;
}

/**
 * @param array<string, mixed> $data
 */
function cx_write_json(string $path, array $data): void
{
    file_put_contents($path, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
}

/**
 * @return array<string, mixed>
 */
function cx_parse_headers_lines(array $lines): array
{
    $statusLine = null;
    /** @var array<string, array<int, string>> $headers */
    $headers = [];

    foreach ($lines as $line) {
        $line = trim((string) $line);
        if ($line === '') {
            continue;
        }

        if (str_starts_with($line, 'HTTP/')) {
            $statusLine = $line;
            continue;
        }

        $pos = strpos($line, ':');
        if ($pos === false) {
            continue;
        }

        $name = strtolower(trim(substr($line, 0, $pos)));
        $value = trim(substr($line, $pos + 1));
        if ($name === '') {
            continue;
        }
        $headers[$name] ??= [];
        $headers[$name][] = $value;
    }

    return [
        'status_line' => $statusLine,
        'headers' => $headers,
    ];
}

function cx_content_type_base(string $contentType): string
{
    $contentType = trim($contentType);
    if ($contentType === '') {
        return '';
    }
    $semi = strpos($contentType, ';');
    if ($semi === false) {
        return strtolower($contentType);
    }
    return strtolower(trim(substr($contentType, 0, $semi)));
}

function cx_is_gzip_bytes(string $bytes): bool
{
    // gzip magic: 1f 8b
    return strlen($bytes) >= 2 && ord($bytes[0]) === 0x1f && ord($bytes[1]) === 0x8b;
}

function cx_hash_file_sha256(?string $path): ?string
{
    if (!is_string($path) || $path === '' || !is_file($path)) {
        return null;
    }
    $h = hash_file('sha256', $path);
    return is_string($h) ? $h : null;
}

/**
 * Attempt to parse rows from common JSON shapes.
 *
 * @param mixed $json
 * @param int $maxRows
 * @return array<int, array<string, mixed>>
 */
function cx_extract_rows(mixed $json, int $maxRows = 0): array
{
    $rows = [];

    if (is_array($json)) {
        // Common wrappers:
        foreach (['rows', 'data', 'items', 'value', 'results'] as $k) {
            if (array_key_exists($k, $json) && is_array($json[$k] ?? null)) {
                $rows = $json[$k];
                break;
            }
        }
        if ($rows === []) {
            // either [ {..}, {..} ]
            $rows = $json;
        }
    }

    $out = [];
    foreach ($rows as $r) {
        if (is_array($r)) {
            /** @var array<string, mixed> $r */
            $out[] = $r;
        }
        if ($maxRows > 0 && count($out) >= $maxRows) {
            break;
        }
    }

    return $out;
}

/**
 * @return array<int, array<string, mixed>>
 */
function cx_parse_ndjson_rows(string $path, int $maxRows = 0): array
{
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

/**
 * @return array<int, array<string, mixed>>
 */
function cx_parse_csv_rows(string $path, int $maxRows = 0): array
{
    $fh = fopen($path, 'rb');
    if ($fh === false) {
        return [];
    }

    try {
        $headers = fgetcsv($fh);
        if (!is_array($headers)) {
            return [];
        }
        $headers = array_map(fn ($h) => is_string($h) ? trim($h) : '', $headers);

        $rows = [];
        while (($line = fgetcsv($fh)) !== false) {
            if (!is_array($line)) {
                continue;
            }

            $row = [];
            foreach ($headers as $i => $h) {
                if ($h === '') {
                    continue;
                }
                $row[$h] = $line[$i] ?? null;
            }

            /** @var array<string, mixed> $row */
            $rows[] = $row;
            if ($maxRows > 0 && count($rows) >= $maxRows) {
                break;
            }
        }

        return $rows;
    } finally {
        fclose($fh);
    }
}

/**
 * @param array<int, array<string, mixed>> $rows
 * @return array{row_count:int, columns:array<int,string>}
 */
function cx_rows_stats(array $rows): array
{
    $cols = [];
    foreach ($rows as $r) {
        foreach (array_keys($r) as $k) {
            $cols[(string) $k] = true;
        }
    }

    $columns = array_keys($cols);
    sort($columns);

    return [
        'row_count' => count($rows),
        'columns' => $columns,
    ];
}

/**
 * Heuristic: find embedded file payloads.
 * Looks for common keys like contentBytes/content_bytes + optional name/type.
 *
 * @param mixed $value
 * @return array<int, array{path:string, filename:?string, content_type:?string, content_bytes:string}>
 */
function cx_find_embedded_files(mixed $value, string $path = '$'): array
{
    $found = [];

    if (is_array($value)) {
        $isAssoc = array_keys($value) !== range(0, count($value) - 1);

        if ($isAssoc) {
            $keys = array_change_key_case(array_map('strval', array_keys($value)), CASE_LOWER);
            $map = [];
            foreach (array_keys($value) as $k) {
                $map[strtolower((string) $k)] = (string) $k;
            }

            $contentKey = null;
            foreach (['contentbytes', 'content_bytes', 'filebytes', 'data', 'content'] as $k) {
                if (array_key_exists($k, $map)) {
                    $contentKey = $map[$k];
                    break;
                }
            }

            if ($contentKey !== null && is_string($value[$contentKey] ?? null)) {
                $cb = (string) $value[$contentKey];

                // If it *looks* like base64, treat as an embedded file.
                $looksBase64 = (bool) preg_match('#^[A-Za-z0-9+/=\r\n]+$#', $cb);
                if ($looksBase64 && strlen($cb) >= 32) {
                    $name = null;
                    foreach (['filename', 'file_name', 'name'] as $nk) {
                        if (array_key_exists($nk, $map) && is_string($value[$map[$nk]] ?? null)) {
                            $name = (string) $value[$map[$nk]];
                            break;
                        }
                    }
                    $ctype = null;
                    foreach (['contenttype', 'content_type', 'mimetype', 'mime_type', 'type'] as $tk) {
                        if (array_key_exists($tk, $map) && is_string($value[$map[$tk]] ?? null)) {
                            $ctype = (string) $value[$map[$tk]];
                            break;
                        }
                    }

                    $found[] = [
                        'path' => $path,
                        'filename' => $name,
                        'content_type' => $ctype,
                        'content_bytes' => $cb,
                    ];
                }
            }
        }

        foreach ($value as $k => $v) {
            $childPath = $path;
            if (is_int($k)) {
                $childPath .= '[' . $k . ']';
            } else {
                $childPath .= '.' . (string) $k;
            }
            $found = array_merge($found, cx_find_embedded_files($v, $childPath));
        }
    }

    return $found;
}

function cx_sanitize_filename(string $name): string
{
    $name = trim($name);
    if ($name === '') {
        return 'file.bin';
    }
    $name = preg_replace('#[^A-Za-z0-9._-]+#', '_', $name) ?: 'file.bin';
    $name = ltrim($name, '.');
    return $name !== '' ? $name : 'file.bin';
}

$args = cx_parse_args($argv);
$url = $args['url'];
$redactedUrl = cx_redact_url($url);

if ($url === '') {
    fwrite(STDERR, "Missing URL argument.\n");
    fwrite(STDERR, "Usage: php ingestion/php_cx_request.php 'https://...'\n");
    exit(2);
}

$runId = gmdate('Ymd_His') . '_' . bin2hex(random_bytes(4));
$baseOut = rtrim($args['out_dir'], '/');
$runDir = cx_mkdir_p($baseOut . '/' . $runId);
$filesDir = cx_mkdir_p($runDir . '/files');

$bodyPath = $runDir . '/response.body';
$headersPath = $runDir . '/response.headers.txt';
$metaPath = $runDir . '/manifest.json';
$headersJsonPath = $runDir . '/response.headers.json';
$decodedBodyPath = null;

$ch = curl_init($url);
if ($ch === false) {
    fwrite(STDERR, "Failed to initialize cURL.\n");
    exit(2);
}

$headers = [
    'request_type: php_cx_request',
    'Accept: application/json',
    'User-Agent: cxflow-ingestion/1.0',
];

// Allow extra headers via env JSON (values are treated as secrets and are NOT written to manifest).
$customHeadersRaw = trim((string) ($args['headers_json'] ?? ''));
$customHeaderNames = [];
if ($customHeadersRaw !== '') {
    /** @var mixed $decoded */
    $decoded = json_decode($customHeadersRaw, true);
    if (is_array($decoded)) {
        foreach ($decoded as $k => $v) {
            if (!is_string($k) || $k === '') {
                continue;
            }
            if (!is_string($v)) {
                continue;
            }
            $headers[] = $k . ': ' . $v;
            $customHeaderNames[] = $k;
        }
    }
}

$headerLines = [];
$fh = fopen($bodyPath, 'wb');
if ($fh === false) {
    fwrite(STDERR, "Failed to open output file for response body.\n");
    exit(2);
}

curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => false,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_MAXREDIRS => 3,
    CURLOPT_CONNECTTIMEOUT => (int) ($args['connect_timeout_seconds'] ?? 10),
    CURLOPT_TIMEOUT => (int) ($args['timeout_seconds'] ?? 30),
    CURLOPT_HTTPHEADER => $headers,
    CURLOPT_FILE => $fh,
    CURLOPT_HEADERFUNCTION => static function ($ch, string $header) use (&$headerLines): int {
        $trim = trim($header);
        if ($trim !== '') {
            $headerLines[] = $trim;
        }
        return strlen($header);
    },
]);

$ok = curl_exec($ch);
fclose($fh);

if ($ok === false) {
    $err = curl_error($ch);
    $errno = curl_errno($ch);
    curl_close($ch);

    @file_put_contents($headersPath, implode("\n", $headerLines) . "\n");

    cx_write_json($metaPath, [
        'ok' => false,
        'run_id' => $runId,
        'request' => [
            'method' => 'GET',
            'url_redacted' => $redactedUrl,
            'headers' => ['request_type' => 'php_cx_request'],
        ],
        'error' => [
            'type' => 'curl_failed',
            'curl_errno' => $errno,
            'message' => $err,
        ],
        'artifacts' => [
            'run_dir' => $runDir,
            'response_body' => $bodyPath,
            'response_headers' => $headersPath,
        ],
    ]);

    echo json_encode([
        'ok' => false,
        'error' => 'curl_failed',
        'curl_errno' => $errno,
        'message' => $err,
        'run_id' => $runId,
        'run_dir' => $runDir,
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
    exit(1);
}

$httpCode = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
$contentType = (string) (curl_getinfo($ch, CURLINFO_CONTENT_TYPE) ?: '');
$timings = [
    'total_time' => (float) curl_getinfo($ch, CURLINFO_TOTAL_TIME),
    'namelookup_time' => (float) curl_getinfo($ch, CURLINFO_NAMELOOKUP_TIME),
    'connect_time' => (float) curl_getinfo($ch, CURLINFO_CONNECT_TIME),
    'appconnect_time' => (float) curl_getinfo($ch, CURLINFO_APPCONNECT_TIME),
    'pretransfer_time' => (float) curl_getinfo($ch, CURLINFO_PRETRANSFER_TIME),
    'starttransfer_time' => (float) curl_getinfo($ch, CURLINFO_STARTTRANSFER_TIME),
    'redirect_time' => (float) curl_getinfo($ch, CURLINFO_REDIRECT_TIME),
    'redirect_count' => (int) curl_getinfo($ch, CURLINFO_REDIRECT_COUNT),
    'size_download' => (float) curl_getinfo($ch, CURLINFO_SIZE_DOWNLOAD),
];
curl_close($ch);

$rawHeaders = implode("\n", $headerLines) . "\n";
file_put_contents($headersPath, $rawHeaders);

$parsedHeaders = cx_parse_headers_lines($headerLines);
cx_write_json($headersJsonPath, $parsedHeaders);

$bodySize = is_file($bodyPath) ? (int) filesize($bodyPath) : 0;

$isSuccess = $httpCode >= 200 && $httpCode < 300;
$parsedJson = null;
$parsedJsonPath = null;
$rowsPath = null;
$rowsCsvPath = null;
$fileArtifacts = [];
$rowStats = null;

$parseEnabled = $isSuccess || (bool) ($args['parse_on_failure'] ?? true);

// On success (or when enabled), aggressively process the response into useful artifacts.
if ($parseEnabled) {
    $sniff = '';
    $fh2 = fopen($bodyPath, 'rb');
    if ($fh2 !== false) {
        $sniff = (string) fread($fh2, 4096);
        fclose($fh2);
    }
    $sniffTrim = ltrim($sniff);

    $baseType = cx_content_type_base($contentType);
    $looksJson = str_contains($baseType, 'json') || str_starts_with($sniffTrim, '{') || str_starts_with($sniffTrim, '[');
    $looksNdjson = str_contains($baseType, 'ndjson') || str_contains($baseType, 'jsonl');
    $looksCsv = str_contains($baseType, 'csv') || str_contains($baseType, 'text/csv');

    // If response is gzip, optionally decode for parsing (keeps raw body always).
    $parsePath = $bodyPath;
    $contentEncoding = '';
    /** @var array<string, array<int, string>> $hdrMap */
    $hdrMap = is_array($parsedHeaders['headers'] ?? null) ? $parsedHeaders['headers'] : [];
    if (isset($hdrMap['content-encoding'][0])) {
        $contentEncoding = strtolower((string) $hdrMap['content-encoding'][0]);
    }

    $sniffIsGz = cx_is_gzip_bytes($sniff);
    $encodingSaysGz = str_contains($contentEncoding, 'gzip');
    if ((bool) ($args['decode_gzip'] ?? true) && ($sniffIsGz || $encodingSaysGz) && $bodySize > 0) {
        // Decode only when body is within max_parse_bytes to avoid accidental huge decompression.
        $maxParse = (int) ($args['max_parse_bytes'] ?? 25_000_000);
        if ($maxParse <= 0 || $bodySize <= $maxParse) {
            $rawBody = (string) file_get_contents($bodyPath);
            $decodedBody = function_exists('gzdecode') ? @gzdecode($rawBody) : false;
            if (is_string($decodedBody) && $decodedBody !== '') {
                $decodedBodyPath = $runDir . '/response.decoded.body';
                file_put_contents($decodedBodyPath, $decodedBody);
                $parsePath = $decodedBodyPath;
            }
        }
    }

    $maxParseBytes = (int) ($args['max_parse_bytes'] ?? 25_000_000);
    $maxRows = (int) ($args['max_rows'] ?? 5000);

    // Keep parsing bounded. (Still saves raw body regardless.)
    $parseSize = is_file($parsePath) ? (int) filesize($parsePath) : 0;
    $withinParseLimit = $parseSize > 0 && ($maxParseBytes <= 0 || $parseSize <= $maxParseBytes);

    // Try JSON first.
    if (($looksJson || $looksNdjson) && $withinParseLimit) {
        $rawBody = (string) file_get_contents($parsePath);
        $decoded = json_decode($rawBody, true);
        if (is_array($decoded)) {
            $parsedJson = $decoded;
            $parsedJsonPath = $runDir . '/response.json';
            file_put_contents($parsedJsonPath, json_encode($decoded, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");

            $rows = cx_extract_rows($decoded, $maxRows);
            if (count($rows) > 0) {
                $rowStats = cx_rows_stats($rows);

                // NDJSON is the most robust format for downstream automation.
                $rowsPath = $runDir . '/rows.ndjson';
                $nd = fopen($rowsPath, 'wb');
                if ($nd !== false) {
                    foreach ($rows as $r) {
                        fwrite($nd, json_encode($r, JSON_UNESCAPED_SLASHES) . "\n");
                    }
                    fclose($nd);
                }

                // Optional CSV (best-effort)
                $rowsCsvPath = $runDir . '/rows.csv';
                $csv = fopen($rowsCsvPath, 'wb');
                if ($csv !== false) {
                    $columns = $rowStats['columns'] ?? [];
                    fputcsv($csv, $columns);
                    foreach ($rows as $r) {
                        $line = [];
                        foreach ($columns as $c) {
                            $v = $r[$c] ?? null;
                            if (is_array($v) || is_object($v)) {
                                $v = json_encode($v, JSON_UNESCAPED_SLASHES);
                            }
                            $line[] = $v;
                        }
                        fputcsv($csv, $line);
                    }
                    fclose($csv);
                }
            }

            // Extract embedded file payloads if requested.
            if ((bool) ($args['decode_files'] ?? true)) {
                $embedded = cx_find_embedded_files($decoded);
                $totalDecoded = 0;
                $i = 0;
                foreach ($embedded as $e) {
                    $remaining = (int) ($args['max_decode_bytes'] ?? 0);
                    if ($remaining > 0) {
                        $remaining = $remaining - $totalDecoded;
                        if ($remaining <= 0) {
                            break;
                        }
                    }

                    $b64 = (string) ($e['content_bytes'] ?? '');
                    $b64 = trim($b64);
                    if ($b64 === '') {
                        continue;
                    }

                    // Rough pre-check to avoid decoding enormous payloads.
                    if ($remaining > 0) {
                        $pred = (int) floor(strlen($b64) * 0.75);
                        if ($pred > $remaining) {
                            continue;
                        }
                    }

                    // Support data URLs.
                    if (str_starts_with($b64, 'data:') && str_contains($b64, ';base64,')) {
                        $b64 = (string) substr($b64, strpos($b64, ';base64,') + 8);
                    }

                    $bin = base64_decode($b64, true);
                    if ($bin === false) {
                        continue;
                    }

                    $len = strlen($bin);
                    if ((int) ($args['max_decode_bytes'] ?? 0) > 0 && ($totalDecoded + $len) > (int) ($args['max_decode_bytes'] ?? 0)) {
                        continue;
                    }

                    $name = $e['filename'] ?? null;
                    $safe = cx_sanitize_filename(is_string($name) ? $name : ("file_" . $i . ".bin"));
                    $out = $filesDir . '/' . $safe;
                    file_put_contents($out, $bin);

                    $fileArtifacts[] = [
                        'path' => (string) ($e['path'] ?? '$'),
                        'filename' => $safe,
                        'bytes' => $len,
                        'sha256' => cx_hash_file_sha256($out),
                        'content_type' => $e['content_type'] ?? null,
                        'saved_to' => $out,
                    ];
                    $totalDecoded += $len;
                    $i++;
                }
            }
        }
    }

    // If JSON parsing didn't produce rows, try NDJSON.
    if ($rowsPath === null && ($looksNdjson || str_ends_with(strtolower($parsePath), '.ndjson')) && $withinParseLimit) {
        $rows = cx_parse_ndjson_rows($parsePath, $maxRows);
        if (count($rows) > 0) {
            $rowStats = cx_rows_stats($rows);
            $rowsPath = $runDir . '/rows.ndjson';
            $nd = fopen($rowsPath, 'wb');
            if ($nd !== false) {
                foreach ($rows as $r) {
                    fwrite($nd, json_encode($r, JSON_UNESCAPED_SLASHES) . "\n");
                }
                fclose($nd);
            }
        }
    }

    // If still no rows, try CSV.
    if ($rowsPath === null && ($looksCsv || str_ends_with(strtolower($parsePath), '.csv')) && $withinParseLimit) {
        $rows = cx_parse_csv_rows($parsePath, $maxRows);
        if (count($rows) > 0) {
            $rowStats = cx_rows_stats($rows);
            $rowsPath = $runDir . '/rows.ndjson';
            $nd = fopen($rowsPath, 'wb');
            if ($nd !== false) {
                foreach ($rows as $r) {
                    fwrite($nd, json_encode($r, JSON_UNESCAPED_SLASHES) . "\n");
                }
                fclose($nd);
            }
            $rowsCsvPath = $runDir . '/rows.csv';
            // Keep original CSV copy for convenience.
            if ($parsePath !== $rowsCsvPath) {
                @copy($parsePath, $rowsCsvPath);
            }
        }
    }
}

$bodySnippet = '';
if ($bodySize > 0) {
    $snippetRaw = (string) file_get_contents($bodyPath, false, null, 0, 4000);
    $bodySnippet = $snippetRaw;
}

$manifest = [
    'ok' => $isSuccess,
    'run_id' => $runId,
    'started_at' => gmdate('c'),
    'request' => [
        'method' => 'GET',
        'url_redacted' => $redactedUrl,
        'headers' => [
            'request_type' => 'php_cx_request',
            'custom_header_names' => $customHeaderNames,
        ],
    ],
    'response' => [
        'http_code' => $httpCode,
        'content_type' => $contentType,
        'body_bytes' => $bodySize,
        'body_snippet' => $bodySnippet,
        'headers_parsed' => $parsedHeaders,
        'timings' => $timings,
    ],
    'processing' => [
        'parsed_json' => $parsedJson !== null,
        'rows_extracted' => $rowsPath !== null,
        'row_stats' => $rowStats,
        'decoded_files' => $fileArtifacts,
    ],
    'checksums' => [
        'response_body_sha256' => cx_hash_file_sha256($bodyPath),
        'response_json_sha256' => cx_hash_file_sha256($parsedJsonPath),
        'rows_ndjson_sha256' => cx_hash_file_sha256($rowsPath),
        'rows_csv_sha256' => cx_hash_file_sha256($rowsCsvPath),
        'response_headers_sha256' => cx_hash_file_sha256($headersPath),
        'response_headers_json_sha256' => cx_hash_file_sha256($headersJsonPath),
    ],
    'artifacts' => [
        'run_dir' => $runDir,
        'response_headers' => $headersPath,
        'response_headers_json' => $headersJsonPath,
        'response_body' => $bodyPath,
        'response_json' => $parsedJsonPath,
        'rows_ndjson' => $rowsPath,
        'rows_csv' => $rowsCsvPath,
        'files_dir' => $filesDir,
    ],
];

cx_write_json($metaPath, $manifest);

echo json_encode([
    // Keep stdout a clean, compact summary; full details are written to manifest.json.
    'ok' => $isSuccess,
    'run_id' => $runId,
    'run_dir' => $runDir,
    'manifest' => $metaPath,
    'response' => [
        'http_code' => $httpCode,
        'content_type' => $contentType,
        'body_bytes' => $bodySize,
    ],
    'processing' => [
        'parsed_json' => $parsedJson !== null,
        'rows_ndjson' => $rowsPath,
        'rows_csv' => $rowsCsvPath,
        'decoded_files_count' => count($fileArtifacts),
    ],
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";

exit($isSuccess ? 0 : 1);
