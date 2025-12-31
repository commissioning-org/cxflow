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

$url = $argv[1] ?? '';
$url = trim((string) $url);

if ($url === '') {
    fwrite(STDERR, "Missing URL argument.\n");
    fwrite(STDERR, "Usage: php ingestion/php_cx_request.php 'https://...'\n");
    exit(2);
}

$ch = curl_init($url);
if ($ch === false) {
    fwrite(STDERR, "Failed to initialize cURL.\n");
    exit(2);
}

$headers = [
    'request_type: php_cx_request',
    'Accept: application/json',
];

curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_MAXREDIRS => 3,
    CURLOPT_CONNECTTIMEOUT => 10,
    CURLOPT_TIMEOUT => 30,
    CURLOPT_HTTPHEADER => $headers,
    CURLOPT_HEADER => true,
]);

$response = curl_exec($ch);
if ($response === false) {
    $err = curl_error($ch);
    $errno = curl_errno($ch);
    curl_close($ch);

    echo json_encode([
        'ok' => false,
        'error' => 'curl_failed',
        'curl_errno' => $errno,
        'message' => $err,
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
    exit(1);
}

$httpCode = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
$headerSize = (int) curl_getinfo($ch, CURLINFO_HEADER_SIZE);
curl_close($ch);

$rawHeaders = substr($response, 0, $headerSize);
$body = substr($response, $headerSize);

echo json_encode([
    'ok' => $httpCode >= 200 && $httpCode < 300,
    'request' => [
        'method' => 'GET',
        // Avoid echoing the full URL (it may contain a signature). Show only host/path.
        'url_redacted' => preg_replace('#(\?.*)$#', '?<redacted>', $url) ?: '<redacted>',
        'headers' => [
            'request_type' => 'php_cx_request',
        ],
    ],
    'response' => [
        'http_code' => $httpCode,
        'headers_raw' => $rawHeaders,
        'body' => $body,
    ],
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
