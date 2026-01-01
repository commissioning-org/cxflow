<?php

declare(strict_types=1);

/**
 * Auto-validation module for ingestion data quality checks.
 *
 * Provides automated validation of ingested data with:
 * - Schema detection and validation
 * - Data quality metrics
 * - Anomaly detection
 * - Automatic data cleaning suggestions
 * - Compliance checks
 *
 * Usage:
 *   $validator = new AutoValidator($manifest);
 *   $result = $validator->validate();
 */

class DataQualityMetrics
{
    public float $completeness = 0.0;  // % of non-null values
    public float $consistency = 0.0;   // % of consistent data types
    public float $validity = 0.0;      // % of valid values
    public float $accuracy = 0.0;      // % of accurate values (if ground truth exists)
    public int $totalRows = 0;
    public int $totalColumns = 0;
    public int $duplicateRows = 0;
    public int $nullValues = 0;
    public array $columnStats = [];
    public array $anomalies = [];
    public array $warnings = [];
    public array $suggestions = [];
}

class AutoValidator
{
    private array $manifest;
    private DataQualityMetrics $metrics;
    private array $config;

    public function __construct(array $manifest, array $config = [])
    {
        $this->manifest = $manifest;
        $this->metrics = new DataQualityMetrics();
        $this->config = array_merge([
            'min_completeness' => 0.7,
            'min_consistency' => 0.8,
            'detect_anomalies' => true,
            'suggest_fixes' => true,
            'check_duplicates' => true,
            'max_null_percentage' => 0.3,
        ], $config);
    }

    public function validate(): array
    {
        $startTime = microtime(true);

        // Load data from manifest
        $rowsPath = $this->manifest['artifacts']['rows_ndjson'] ?? null;
        if (!is_string($rowsPath) || !is_file($rowsPath)) {
            return [
                'ok' => false,
                'error' => 'no_data_to_validate',
                'metrics' => $this->metrics
            ];
        }

        $rows = $this->loadRows($rowsPath);
        if (empty($rows)) {
            return [
                'ok' => false,
                'error' => 'empty_dataset',
                'metrics' => $this->metrics
            ];
        }

        $this->metrics->totalRows = count($rows);

        // Analyze schema
        $schema = $this->detectSchema($rows);

        // Calculate metrics
        $this->calculateCompleteness($rows, $schema);
        $this->calculateConsistency($rows, $schema);
        $this->detectDuplicates($rows);

        if ($this->config['detect_anomalies']) {
            $this->detectAnomalies($rows, $schema);
        }

        if ($this->config['suggest_fixes']) {
            $this->generateSuggestions();
        }

        $elapsedMs = (int)((microtime(true) - $startTime) * 1000);

        // Overall quality score
        $qualityScore = ($this->metrics->completeness + $this->metrics->consistency) / 2;
        $passed = $qualityScore >= $this->config['min_completeness'];

        return [
            'ok' => $passed,
            'quality_score' => round($qualityScore, 2),
            'metrics' => [
                'completeness' => round($this->metrics->completeness, 2),
                'consistency' => round($this->metrics->consistency, 2),
                'total_rows' => $this->metrics->totalRows,
                'total_columns' => $this->metrics->totalColumns,
                'duplicate_rows' => $this->metrics->duplicateRows,
                'null_values' => $this->metrics->nullValues,
                'column_stats' => $this->metrics->columnStats,
                'anomalies' => $this->metrics->anomalies,
                'warnings' => $this->metrics->warnings,
            ],
            'suggestions' => $this->metrics->suggestions,
            'schema' => $schema,
            'elapsed_ms' => $elapsedMs,
            'timestamp' => gmdate('Y-m-d\TH:i:s\Z'),
        ];
    }

    private function loadRows(string $path, int $maxRows = 10000): array
    {
        $fh = fopen($path, 'rb');
        if ($fh === false) {
            return [];
        }

        $rows = [];
        try {
            while (!feof($fh) && count($rows) < $maxRows) {
                $line = fgets($fh);
                if ($line === false) {
                    break;
                }
                $line = trim($line);
                if ($line === '') {
                    continue;
                }
                $json = json_decode($line, true);
                if (is_array($json)) {
                    $rows[] = $json;
                }
            }
        } finally {
            fclose($fh);
        }

        return $rows;
    }

    private function detectSchema(array $rows): array
    {
        if (empty($rows)) {
            return [];
        }

        $schema = [];
        $sample = array_slice($rows, 0, min(100, count($rows)));

        // Get all unique keys
        $allKeys = [];
        foreach ($sample as $row) {
            $allKeys = array_merge($allKeys, array_keys($row));
        }
        $allKeys = array_unique($allKeys);
        $this->metrics->totalColumns = count($allKeys);

        // Analyze each column
        foreach ($allKeys as $key) {
            $values = array_filter(
                array_map(fn($row) => $row[$key] ?? null, $sample),
                fn($v) => $v !== null
            );

            $types = array_unique(array_map('gettype', $values));
            $nonNullCount = count($values);
            $nullCount = count($sample) - $nonNullCount;

            $schema[$key] = [
                'types' => $types,
                'primary_type' => $this->determinePrimaryType($values),
                'nullable' => $nullCount > 0,
                'null_percentage' => round($nullCount / count($sample), 2),
                'sample_values' => array_slice($values, 0, 3),
            ];

            // Add numeric statistics if applicable
            if ($schema[$key]['primary_type'] === 'numeric') {
                $numericValues = array_filter($values, 'is_numeric');
                if (!empty($numericValues)) {
                    $schema[$key]['min'] = min($numericValues);
                    $schema[$key]['max'] = max($numericValues);
                    $schema[$key]['avg'] = array_sum($numericValues) / count($numericValues);
                }
            }
        }

        return $schema;
    }

    private function determinePrimaryType(array $values): string
    {
        if (empty($values)) {
            return 'unknown';
        }

        $typeCounts = array_count_values(array_map('gettype', $values));
        arsort($typeCounts);
        $mostCommonType = array_key_first($typeCounts);

        // Map PHP types to semantic types
        $typeMap = [
            'integer' => 'numeric',
            'double' => 'numeric',
            'string' => 'string',
            'boolean' => 'boolean',
            'array' => 'array',
            'object' => 'object',
        ];

        return $typeMap[$mostCommonType] ?? 'unknown';
    }

    private function calculateCompleteness(array $rows, array $schema): void
    {
        $totalCells = count($rows) * count($schema);
        if ($totalCells === 0) {
            $this->metrics->completeness = 0.0;
            return;
        }

        $nullCount = 0;
        foreach ($rows as $row) {
            foreach (array_keys($schema) as $key) {
                if (!isset($row[$key]) || $row[$key] === null || $row[$key] === '') {
                    $nullCount++;
                }
            }
        }

        $this->metrics->nullValues = $nullCount;
        $this->metrics->completeness = 1.0 - ($nullCount / $totalCells);

        if ($this->metrics->completeness < $this->config['min_completeness']) {
            $this->metrics->warnings[] = sprintf(
                'Low data completeness: %.1f%% (minimum: %.1f%%)',
                $this->metrics->completeness * 100,
                $this->config['min_completeness'] * 100
            );
        }
    }

    private function calculateConsistency(array $rows, array $schema): void
    {
        $totalChecks = 0;
        $consistentChecks = 0;

        foreach ($rows as $row) {
            foreach ($schema as $key => $colSchema) {
                if (!isset($row[$key])) {
                    continue;
                }

                $totalChecks++;
                $value = $row[$key];
                $expectedType = $colSchema['primary_type'];
                $actualType = $this->determinePrimaryType([$value]);

                if ($expectedType === $actualType) {
                    $consistentChecks++;
                }
            }
        }

        $this->metrics->consistency = $totalChecks > 0 ? $consistentChecks / $totalChecks : 1.0;

        if ($this->metrics->consistency < $this->config['min_consistency']) {
            $this->metrics->warnings[] = sprintf(
                'Low data consistency: %.1f%% (minimum: %.1f%%)',
                $this->metrics->consistency * 100,
                $this->config['min_consistency'] * 100
            );
        }
    }

    private function detectDuplicates(array $rows): void
    {
        if (!$this->config['check_duplicates']) {
            return;
        }

        $hashes = [];
        $duplicates = 0;

        foreach ($rows as $row) {
            $hash = md5(json_encode($row));
            if (isset($hashes[$hash])) {
                $duplicates++;
            } else {
                $hashes[$hash] = true;
            }
        }

        $this->metrics->duplicateRows = $duplicates;

        if ($duplicates > 0) {
            $this->metrics->warnings[] = sprintf(
                'Found %d duplicate rows (%.1f%%)',
                $duplicates,
                ($duplicates / count($rows)) * 100
            );
        }
    }

    private function detectAnomalies(array $rows, array $schema): void
    {
        // Simple anomaly detection for numeric columns
        foreach ($schema as $key => $colSchema) {
            if ($colSchema['primary_type'] !== 'numeric') {
                continue;
            }

            $values = array_filter(
                array_map(fn($row) => $row[$key] ?? null, $rows),
                fn($v) => $v !== null && is_numeric($v)
            );

            if (count($values) < 10) {
                continue;
            }

            $mean = array_sum($values) / count($values);
            $variance = array_sum(array_map(fn($v) => pow($v - $mean, 2), $values)) / count($values);
            $stdDev = sqrt($variance);

            // Detect outliers (values beyond 3 standard deviations)
            $outliers = array_filter($values, fn($v) => abs($v - $mean) > 3 * $stdDev);

            if (!empty($outliers)) {
                $this->metrics->anomalies[] = [
                    'column' => $key,
                    'type' => 'outliers',
                    'count' => count($outliers),
                    'percentage' => round((count($outliers) / count($values)) * 100, 2),
                    'examples' => array_slice($outliers, 0, 3),
                ];
            }
        }
    }

    private function generateSuggestions(): void
    {
        // Suggest fixes based on metrics
        if ($this->metrics->duplicateRows > 0) {
            $this->metrics->suggestions[] = [
                'type' => 'deduplication',
                'priority' => 'medium',
                'action' => 'Remove duplicate rows',
                'impact' => sprintf('Will reduce dataset by %d rows', $this->metrics->duplicateRows),
            ];
        }

        if ($this->metrics->nullValues > $this->metrics->totalRows * $this->metrics->totalColumns * 0.2) {
            $this->metrics->suggestions[] = [
                'type' => 'imputation',
                'priority' => 'high',
                'action' => 'Consider imputing null values',
                'impact' => sprintf('Will fill %d null values', $this->metrics->nullValues),
            ];
        }

        if (!empty($this->metrics->anomalies)) {
            $this->metrics->suggestions[] = [
                'type' => 'outlier_handling',
                'priority' => 'medium',
                'action' => 'Review and handle outliers',
                'impact' => 'May improve model performance',
            ];
        }
    }
}

/**
 * Run validation on ingestion data.
 *
 * @param array $manifest Ingestion manifest
 * @param array $config Validation config
 * @return array Validation result
 */
function validate_ingestion_data(array $manifest, array $config = []): array
{
    $validator = new AutoValidator($manifest, $config);
    return $validator->validate();
}
