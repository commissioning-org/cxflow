<?php

declare(strict_types=1);

namespace App\Services\MlAutomation;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;

final class DatasetLoader
{
    /**
     * Load rows from http(s) JSON or local CSV/JSON.
     *
     * @return array<int, array<string, mixed>>
     */
    public function loadRows(string $source, string $format = 'auto'): array
    {
        $source = trim($source);
        if ($source === '') {
            return [];
        }

        $format = Str::lower(trim($format));

        if (Str::startsWith($source, ['http://', 'https://'])) {
            return $this->loadFromHttpJson($source);
        }

        // Local file
        $path = $source;
        if (!is_file($path)) {
            // Allow relative paths from project root.
            $candidate = base_path($source);
            if (is_file($candidate)) {
                $path = $candidate;
            }
        }

        if (!is_file($path)) {
            return [];
        }

        if ($format === 'auto') {
            $lower = Str::lower($path);
            if (Str::endsWith($lower, '.csv')) {
                $format = 'csv';
            } elseif (Str::endsWith($lower, '.json')) {
                $format = 'json';
            }
        }

        return match ($format) {
            'csv' => $this->loadFromCsv($path),
            'json' => $this->loadFromJsonFile($path),
            default => $this->loadFromJsonFile($path),
        };
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    private function loadFromHttpJson(string $url): array
    {
        $timeout = (int) config('ml_automation.ingest.timeout_seconds', 30);
        $maxRows = (int) config('ml_automation.ingest.max_rows', 5000);

        $resp = Http::timeout($timeout)->acceptJson()->get($url);
        if (!$resp->ok()) {
            return [];
        }

        /** @var mixed $json */
        $json = $resp->json();
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
            if (count($out) >= $maxRows) {
                break;
            }
        }

        return $out;
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    private function loadFromJsonFile(string $path): array
    {
        $maxRows = (int) config('ml_automation.ingest.max_rows', 5000);

        $raw = (string) file_get_contents($path);
        /** @var mixed $json */
        $json = json_decode($raw, true);

        if (!is_array($json)) {
            return [];
        }

        $rows = [];
        if (array_key_exists('rows', $json) && is_array($json['rows'] ?? null)) {
            $rows = $json['rows'];
        } else {
            $rows = $json;
        }

        $out = [];
        foreach ($rows as $r) {
            if (is_array($r)) {
                /** @var array<string, mixed> $r */
                $out[] = $r;
            }
            if (count($out) >= $maxRows) {
                break;
            }
        }

        return $out;
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    private function loadFromCsv(string $path): array
    {
        $maxRows = (int) config('ml_automation.ingest.max_rows', 5000);

        $fh = fopen($path, 'r');
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
                if (count($rows) >= $maxRows) {
                    break;
                }
            }

            return $rows;
        } finally {
            fclose($fh);
        }
    }
}
