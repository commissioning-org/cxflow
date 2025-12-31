<?php

declare(strict_types=1);

/**
 * Supabase Storage uploader (internal automation helper).
 *
 * Uploads files from an ingestion run directory (or any directory) into a Supabase Storage bucket.
 *
 * Usage:
 *   php ingestion/supabase_upload.php <run_dir>
 *
 * Environment:
 *   SUPABASE_UPLOAD_ENABLED=true|false (default false)
 *   SUPABASE_PROJECT_URL=https://<project>.supabase.co
 *   SUPABASE_STORAGE_BASE_URL=<override> (default: ${SUPABASE_PROJECT_URL}/storage/v1)
 *   SUPABASE_SERVICE_ROLE_KEY=<secret>
 *   SUPABASE_API_KEY=<secret> (optional; if empty, service role is used)
 *   SUPABASE_BUCKET=cx-ingestion
 *   SUPABASE_PREFIX=runs/<run_id> (default: runs/<basename(run_dir)>)
 *   SUPABASE_UPSERT=true|false (default true)
 *   SUPABASE_TIMEOUT_SECONDS=30
 *   SUPABASE_INCLUDE_MANIFEST=true|false (default true)
 *   SUPABASE_INCLUDE_ROWS=true|false (default true)
 *   SUPABASE_INCLUDE_FILES=true|false (default true)
 */

function sb_bool(string $v, bool $default = false): bool
{
    $v = trim($v);
    if ($v === '') {
        return $default;
    }
    return in_array(strtolower($v), ['1', 'true', 'yes', 'on'], true);
}

function sb_join_url(string $base, string $path): string
{
    return rtrim($base, '/') . '/' . ltrim($path, '/');
}

function sb_sanitize_path(string $path): string
{
    $path = str_replace('\\', '/', $path);
    $path = preg_replace('#/+#', '/', $path) ?: $path;
    $path = ltrim($path, '/');
    return $path;
}

function sb_detect_content_type(string $path): string
{
    $lower = strtolower($path);
    if (str_ends_with($lower, '.json')) return 'application/json';
    if (str_ends_with($lower, '.ndjson')) return 'application/x-ndjson';
    if (str_ends_with($lower, '.csv')) return 'text/csv';
    if (str_ends_with($lower, '.txt')) return 'text/plain';
    if (str_ends_with($lower, '.png')) return 'image/png';
    if (str_ends_with($lower, '.jpg') || str_ends_with($lower, '.jpeg')) return 'image/jpeg';
    if (str_ends_with($lower, '.pdf')) return 'application/pdf';
    return 'application/octet-stream';
}

/**
 * Upload object to Supabase Storage.
 *
 * Uses the Storage REST endpoint:
 *   POST {storageBase}/object/{bucket}/{objectPath}
 *
 * @return array{ok:bool,http_code:int,error:?string}
 */
function sb_upload_file(string $storageBase, string $bucket, string $objectPath, string $localPath, string $serviceRoleKey, string $apiKey, bool $upsert, int $timeoutSeconds): array
{
    if (!is_file($localPath)) {
        return ['ok' => false, 'http_code' => 0, 'error' => 'missing_local_file'];
    }

    $bucket = trim($bucket);
    if ($bucket === '') {
        return ['ok' => false, 'http_code' => 0, 'error' => 'missing_bucket'];
    }

    $objectPath = sb_sanitize_path($objectPath);
    if ($objectPath === '') {
        return ['ok' => false, 'http_code' => 0, 'error' => 'missing_object_path'];
    }

    $url = sb_join_url($storageBase, 'object/' . rawurlencode($bucket) . '/' . str_replace('%2F', '/', rawurlencode($objectPath)));

    $ch = curl_init($url);
    if ($ch === false) {
        return ['ok' => false, 'http_code' => 0, 'error' => 'curl_init_failed'];
    }

    $file = new CURLFile($localPath, sb_detect_content_type($localPath), basename($localPath));

    $headers = [
        'Authorization: Bearer ' . $serviceRoleKey,
        'apikey: ' . ($apiKey !== '' ? $apiKey : $serviceRoleKey),
        'x-upsert: ' . ($upsert ? 'true' : 'false'),
        'User-Agent: cxflow-supabase-uploader/1.0',
    ];

    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 2,
        CURLOPT_CONNECTTIMEOUT => min(10, max(1, $timeoutSeconds)),
        CURLOPT_TIMEOUT => max(1, $timeoutSeconds),
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_POSTFIELDS => [
            'file' => $file,
        ],
    ]);

    $resp = curl_exec($ch);
    $errno = curl_errno($ch);
    $err = curl_error($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($resp === false) {
        return ['ok' => false, 'http_code' => $code, 'error' => 'curl_failed:' . $errno . ':' . $err];
    }

    return ['ok' => $code >= 200 && $code < 300, 'http_code' => $code, 'error' => null];
}

/**
 * Upload typical ingestion artifacts from a run directory.
 *
 * @return array<string, mixed>
 */
function sb_upload_run_dir(string $runDir): array
{
    $enabled = sb_bool((string) (getenv('SUPABASE_UPLOAD_ENABLED') ?: 'false'), false);
    if (!$enabled) {
        return ['ok' => false, 'error' => 'disabled'];
    }

    $projectUrl = trim((string) (getenv('SUPABASE_PROJECT_URL') ?: ''));
    $storageBase = trim((string) (getenv('SUPABASE_STORAGE_BASE_URL') ?: ''));
    if ($storageBase === '' && $projectUrl !== '') {
        $storageBase = sb_join_url($projectUrl, 'storage/v1');
    }

    $serviceRole = (string) (getenv('SUPABASE_SERVICE_ROLE_KEY') ?: '');
    $apiKey = (string) (getenv('SUPABASE_API_KEY') ?: '');
    $bucket = (string) (getenv('SUPABASE_BUCKET') ?: 'cx-ingestion');
    $timeout = (int) (getenv('SUPABASE_TIMEOUT_SECONDS') ?: 30);
    $upsert = sb_bool((string) (getenv('SUPABASE_UPSERT') ?: 'true'), true);

    if ($storageBase === '' || $serviceRole === '') {
        return ['ok' => false, 'error' => 'missing_supabase_config'];
    }

    $prefix = (string) (getenv('SUPABASE_PREFIX') ?: '');
    if (trim($prefix) === '') {
        $prefix = 'runs/' . basename(rtrim($runDir, '/'));
    }
    $prefix = sb_sanitize_path($prefix);

    $includeManifest = sb_bool((string) (getenv('SUPABASE_INCLUDE_MANIFEST') ?: 'true'), true);
    $includeRows = sb_bool((string) (getenv('SUPABASE_INCLUDE_ROWS') ?: 'true'), true);
    $includeFiles = sb_bool((string) (getenv('SUPABASE_INCLUDE_FILES') ?: 'true'), true);

    $uploads = [];

    $candidates = [];
    if ($includeManifest) {
        $candidates['manifest.json'] = $runDir . '/manifest.json';
        $candidates['event.json'] = $runDir . '/event.json';
    }
    if ($includeRows) {
        $candidates['rows.ndjson'] = $runDir . '/rows.ndjson';
        $candidates['rows.csv'] = $runDir . '/rows.csv';
        $candidates['response.json'] = $runDir . '/response.json';
    }

    foreach ($candidates as $name => $path) {
        if (!is_file($path)) {
            continue;
        }
        $obj = $prefix . '/' . $name;
        $uploads[$name] = sb_upload_file($storageBase, $bucket, $obj, $path, $serviceRole, $apiKey, $upsert, $timeout);
    }

    if ($includeFiles) {
        $filesDir = $runDir . '/files';
        if (is_dir($filesDir)) {
            $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($filesDir));
            /** @var SplFileInfo $f */
            foreach ($it as $f) {
                if (!$f->isFile()) {
                    continue;
                }
                $local = $f->getPathname();
                $rel = substr($local, strlen(rtrim($filesDir, '/')) + 1);
                $rel = sb_sanitize_path($rel);
                if ($rel === '') {
                    continue;
                }
                $obj = $prefix . '/files/' . $rel;
                $uploads['files/' . $rel] = sb_upload_file($storageBase, $bucket, $obj, $local, $serviceRole, $apiKey, $upsert, $timeout);
            }
        }
    }

    $ok = true;
    foreach ($uploads as $u) {
        if (!is_array($u) || ($u['ok'] ?? false) !== true) {
            $ok = false;
            break;
        }
    }

    return [
        'ok' => $ok,
        'bucket' => $bucket,
        'prefix' => $prefix,
        'upload_count' => count($uploads),
        'uploads' => $uploads,
    ];
}

$runDir = trim((string) ($argv[1] ?? ''));
if ($runDir === '') {
    fwrite(STDERR, "Missing run_dir argument.\n");
    fwrite(STDERR, "Usage: php ingestion/supabase_upload.php <run_dir>\n");
    exit(2);
}

if (!is_dir($runDir)) {
    fwrite(STDERR, "run_dir not found.\n");
    exit(2);
}

$result = sb_upload_run_dir($runDir);

// Never print secrets; result does not include URLs/keys.
echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";

exit(($result['ok'] ?? false) === true ? 0 : 1);
