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
        $result = match ($this->task) {
            'text' => $assistant->text((string) ($this->payload['prompt'] ?? ''), $this->options),
            'json' => $assistant->json((string) ($this->payload['prompt'] ?? ''), $this->options),
            default => throw new \InvalidArgumentException('Unknown task type.'),
        };

        Cache::put($this->resultKey, [
            'ok' => true,
            'result' => $result,
        ], now()->addMinutes(10));
    }

    public function failed(\Throwable $e): void
    {
        Cache::put($this->resultKey, [
            'ok' => false,
            'error' => 'Task failed.',
        ], now()->addMinutes(10));
    }
}
