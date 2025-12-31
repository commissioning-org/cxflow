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
    $url = $argv[1] ?? '';
    $url = trim((string) $url);

    // Defaults
    $outDir = (string) (getenv('CX_INGESTION_OUT_DIR') ?: (dirname(__FILE__) . '/runs'));
    $decodeFiles = (string) (getenv('CX_INGESTION_DECODE_FILES') ?: 'true');
    $maxDecodeBytes = (int) (getenv('CX_INGESTION_MAX_DECODE_BYTES') ?: 20_000_000); // 20MB

    return [
        'url' => $url,
        'out_dir' => $outDir,
        'decode_files' => in_array(strtolower($decodeFiles), ['1', 'true', 'yes', 'on'], true),
        'max_decode_bytes' => max(0, $maxDecodeBytes),
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
 * Attempt to interpret a decoded JSON payload as rows.
 *
 * @param mixed $json
 * @return array<int, array<string, mixed>>
 */
function cx_extract_rows(mixed $json): array
{
    $rows = [];

    if (is_array($json)) {
        // either [ {..}, {..} ] or { rows: [...] }
        if (array_key_exists('rows', $json) && is_array($json['rows'] ?? null)) {
            $rows = $json['rows'];
        } else {
            $rows = $json;
        }
    }

    $out = [];
    foreach ($rows as $r) {
        if (is_array($r)) {
            /** @var array<string, mixed> $r */
            $out[] = $r;
        }
    }

    return $out;
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

$ch = curl_init($url);
if ($ch === false) {
    fwrite(STDERR, "Failed to initialize cURL.\n");
    exit(2);
}

$headers = [
    'request_type: php_cx_request',
    'Accept: application/json',
];

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
    CURLOPT_CONNECTTIMEOUT => 10,
    CURLOPT_TIMEOUT => 30,
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
curl_close($ch);

$rawHeaders = implode("\n", $headerLines) . "\n";
file_put_contents($headersPath, $rawHeaders);

$bodySize = is_file($bodyPath) ? (int) filesize($bodyPath) : 0;

$isSuccess = $httpCode >= 200 && $httpCode < 300;
$parsedJson = null;
$parsedJsonPath = null;
$rowsPath = null;
$rowsCsvPath = null;
$fileArtifacts = [];
$rowStats = null;

// On success, aggressively process the response into useful artifacts.
if ($isSuccess) {
    $sniff = '';
    $fh2 = fopen($bodyPath, 'rb');
    if ($fh2 !== false) {
        $sniff = (string) fread($fh2, 2048);
        fclose($fh2);
    }
    $sniffTrim = ltrim($sniff);

    $looksJson = str_contains(strtolower($contentType), 'json') || str_starts_with($sniffTrim, '{') || str_starts_with($sniffTrim, '[');

    // Keep parsing bounded. (Still saves raw body regardless.)
    if ($looksJson && $bodySize > 0 && $bodySize <= 25_000_000) { // 25MB
        $rawBody = (string) file_get_contents($bodyPath);
        $decoded = json_decode($rawBody, true);
        if (is_array($decoded)) {
            $parsedJson = $decoded;
            $parsedJsonPath = $runDir . '/response.json';
            file_put_contents($parsedJsonPath, json_encode($decoded, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");

            $rows = cx_extract_rows($decoded);
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

                // Optional CSV (best-effort): only write if values are scalars/null.
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
            if ($args['decode_files']) {
                $embedded = cx_find_embedded_files($decoded);
                $totalDecoded = 0;
                $i = 0;
                foreach ($embedded as $e) {
                    if ($args['max_decode_bytes'] > 0 && $totalDecoded >= $args['max_decode_bytes']) {
                        break;
                    }

                    $b64 = (string) ($e['content_bytes'] ?? '');
                    $bin = base64_decode($b64, true);
                    if ($bin === false) {
                        continue;
                    }

                    $len = strlen($bin);
                    if ($args['max_decode_bytes'] > 0 && ($totalDecoded + $len) > $args['max_decode_bytes']) {
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
                        'content_type' => $e['content_type'] ?? null,
                        'saved_to' => $out,
                    ];
                    $totalDecoded += $len;
                    $i++;
                }
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
    'request' => [
        'method' => 'GET',
        'url_redacted' => $redactedUrl,
        'headers' => [
            'request_type' => 'php_cx_request',
        ],
    ],
    'response' => [
        'http_code' => $httpCode,
        'content_type' => $contentType,
        'body_bytes' => $bodySize,
        'body_snippet' => $bodySnippet,
    ],
    'processing' => [
        'parsed_json' => $parsedJson !== null,
        'rows_extracted' => $rowsPath !== null,
        'row_stats' => $rowStats,
        'decoded_files' => $fileArtifacts,
    ],
    'artifacts' => [
        'run_dir' => $runDir,
        'response_headers' => $headersPath,
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
