<?php

declare(strict_types=1);

namespace App\Services\MlAutomation;

use Illuminate\Support\Str;

/**
 * Centralized webhook payload sampling, redaction, and preparation.
 *
 * Ensures consistent behavior across AutoML and ML automation webhooks.
 */
final class WebhookPayloadHelper
{
    /**
     * Prepare payload with sampling and redaction applied consistently.
     *
     * @param array<string, mixed> $config Webhook configuration
     * @param array<int, array<string, mixed>> $rows Raw data rows
     * @param array<string, mixed> $additionalData Extra fields to merge
     * @return array<string, mixed>
     */
    public static function preparePayload(array $config, array $rows, array $additionalData = []): array
    {
        $fullPayload = (bool) ($config['full_payload'] ?? false);
        
        // full_payload forces include_rows=true and sampling=0
        $includeRows = $fullPayload ? true : (bool) ($config['include_rows'] ?? false);
        $sampleRows = $fullPayload ? 0 : max(0, (int) ($config['sample_rows'] ?? 50));
        
        $rowSample = ($sampleRows > 0 && count($rows) > 0) ? array_slice($rows, 0, $sampleRows) : [];
        
        $payload = [
            'row_count' => count($rows),
            'row_sample' => $rowSample,
            ...$additionalData,
        ];
        
        if ($includeRows) {
            $payload['rows'] = $rows;
        }
        
        return self::redactSensitiveKeys($payload, $config);
    }

    /**
     * Redact or truncate sensitive keys in the payload.
     *
     * @param array<string, mixed> $payload
     * @param array<string, mixed> $config
     * @return array<string, mixed>
     */
    public static function redactSensitiveKeys(array $payload, array $config): array
    {
        $redactKeys = array_map(
            fn($x) => Str::lower((string) $x),
            (array) ($config['redact_keys'] ?? [])
        );
        
        $truncateLength = (int) ($config['truncate_length'] ?? 0);
        
        if (empty($redactKeys) && $truncateLength === 0) {
            return $payload;
        }
        
        return self::walkAndRedact($payload, $redactKeys, $truncateLength);
    }

    /**
     * Recursively walk array and redact/truncate sensitive keys.
     *
     * @param mixed $value
     * @param array<int, string> $redactKeys
     * @return mixed
     */
    private static function walkAndRedact(mixed $value, array $redactKeys, int $truncateLength): mixed
    {
        if (!is_array($value)) {
            return $value;
        }
        
        $result = [];
        foreach ($value as $key => $val) {
            $lowerKey = is_string($key) ? Str::lower($key) : '';
            
            // Redact if key matches redact list
            if ($lowerKey !== '' && in_array($lowerKey, $redactKeys, true)) {
                $result[$key] = '[REDACTED]';
                continue;
            }
            
            // Truncate strings if configured
            if (is_string($val) && $truncateLength > 0 && strlen($val) > $truncateLength) {
                $result[$key] = substr($val, 0, $truncateLength) . '...';
                continue;
            }
            
            // Recurse for nested arrays
            if (is_array($val)) {
                $result[$key] = self::walkAndRedact($val, $redactKeys, $truncateLength);
                continue;
            }
            
            $result[$key] = $val;
        }
        
        return $result;
    }

    /**
     * Add trace_id to payload if provided.
     *
     * @param array<string, mixed> $payload
     * @return array<string, mixed>
     */
    public static function withTraceId(array $payload, ?string $traceId): array
    {
        if ($traceId !== null && $traceId !== '') {
            $payload['trace_id'] = $traceId;
        }
        
        return $payload;
    }
}
