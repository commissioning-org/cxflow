<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Services\Automl\AutomlClient;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Cache;

final class TrainAutomlModel implements ShouldQueue
{
    use Dispatchable;
    use InteractsWithQueue;
    use Queueable;
    use SerializesModels;

    /**
     * @param array<int, array<string, mixed>> $rows
     */
    public function __construct(
        public readonly array $rows,
        public readonly string $target,
        public readonly string $resultKey,
        public readonly ?string $problem = null,
        public readonly ?string $metric = null,
    ) {
    }

    public function handle(AutomlClient $client): void
    {
        $result = $client->train($this->rows, $this->target, $this->problem, $this->metric);

        Cache::put($this->resultKey, [
            'ok' => true,
            'result' => $result,
        ], now()->addMinutes(30));
    }

    public function failed(\Throwable $e): void
    {
        Cache::put($this->resultKey, [
            'ok' => false,
            'error' => 'Training failed.',
        ], now()->addMinutes(30));
    }
}
