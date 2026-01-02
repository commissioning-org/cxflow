<?php

declare(strict_types=1);

namespace App\Services\MlAutomation;

use Illuminate\Support\Str;

/**
 * Helper for generating and managing trace IDs across ML operations.
 */
final class TraceHelper
{
    /**
     * Generate a new trace ID.
     */
    public static function generate(): string
    {
        return (string) Str::uuid();
    }

    /**
     * Extract trace_id from context or generate new one.
     *
     * @param array<string, mixed> $context
     */
    public static function fromContext(array $context): string
    {
        $traceId = $context['trace_id'] ?? null;
        
        if (is_string($traceId) && $traceId !== '') {
            return $traceId;
        }
        
        return self::generate();
    }
}
