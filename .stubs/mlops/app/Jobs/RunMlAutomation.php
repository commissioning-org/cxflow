<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Services\MlAutomation\MlAutomationPipeline;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;

/**
 * Queueable end-to-end ML automation.
 *
 * Stores the run artifact into cache so internal callers can poll by key.
 */
final class RunMlAutomation implements ShouldQueue
{
    use Dispatchable;
    use InteractsWithQueue;
    use Queueable;
    use SerializesModels;

    /**
     * @param array<string, mixed> $overrides
     */
    public function __construct(
        public readonly string $pipeline,
        public readonly string $resultKey,
        public readonly array $overrides = [],
    ) {
    }

    public function handle(MlAutomationPipeline $pipeline): void
    {
        $traceId = (string) Str::uuid();
        $ttl = (int) config('ml_automation.ingest.timeout_seconds', 30) + 600;

        $artifact = $pipeline->run($this->pipeline, $this->overrides);

        Cache::put($this->resultKey, [
            'ok' => true,
            'trace_id' => $traceId,
            'pipeline' => $this->pipeline,
            'artifact' => $artifact,
        ], now()->addSeconds($ttl));
    }

    public function failed(\Throwable $e): void
    {
        Cache::put($this->resultKey, [
            'ok' => false,
            'error' => 'ML automation failed.',
        ], now()->addMinutes(10));
    }
}
