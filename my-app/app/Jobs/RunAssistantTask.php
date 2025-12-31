<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Services\Assistant\AssistantService;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;

/**
 * Generic automation job.
 *
 * Stores result into cache under a result key so your app can poll internally
 * (without exposing any AI/provider details externally).
 */
final class RunAssistantTask implements ShouldQueue
{
    use Dispatchable;
    use InteractsWithQueue;
    use Queueable;
    use SerializesModels;

    /**
     * @param array<string, mixed> $payload
     * @param array<string, mixed> $options
     */
    public function __construct(
        public readonly string $task,
        public readonly array $payload,
        public readonly string $resultKey,
        public readonly array $options = [],
    ) {
    }

    public function handle(AssistantService $assistant): void
    {
        $traceId = (string) Str::uuid();
        $startedAt = now();

        $result = match ($this->task) {
            'text' => $assistant->text((string) ($this->payload['prompt'] ?? ''), $this->options),
            'json' => $assistant->json((string) ($this->payload['prompt'] ?? ''), $this->options),
            default => throw new \InvalidArgumentException('Unknown task type.'),
        };

        Cache::put($this->resultKey, [
            'ok' => true,
            'trace_id' => $traceId,
            'task' => $this->task,
            'started_at' => $startedAt->toIso8601String(),
            'finished_at' => now()->toIso8601String(),
            'result' => $result,
        ], now()->addSeconds((int) config('assistant.cache.ttl_seconds', 600)));
    }

    public function failed(\Throwable $e): void
    {
        Cache::put($this->resultKey, [
            'ok' => false,
            'error' => 'Task failed.',
        ], now()->addSeconds((int) config('assistant.cache.ttl_seconds', 600)));
    }
}
