<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Services\Superset\SupersetClient;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;

/**
 * Execute Query Job
 *
 * Asynchronously executes SQL queries via Superset SQL Lab.
 */
final class ExecuteQuery implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $timeout = 600;
    public int $tries = 2;

    public function __construct(
        private readonly int $databaseId,
        private readonly string $sql,
        private readonly ?string $schema = null,
        private readonly int $limit = 1000,
        private readonly ?string $resultKey = null
    ) {
    }

    public function handle(SupersetClient $client): void
    {
        try {
            Log::info('Starting SQL query execution', [
                'database_id' => $this->databaseId,
                'sql' => substr($this->sql, 0, 200),
                'schema' => $this->schema,
            ]);

            $client->authenticate();
            $result = $client->executeSql(
                $this->databaseId,
                $this->sql,
                $this->schema,
                $this->limit,
                false // Execute synchronously in the job
            );

            $result['executed_at'] = now()->toIso8601String();
            $result['status'] = $result['status'] ?? 'success';

            if ($this->resultKey) {
                Cache::put($this->resultKey, $result, now()->addHours(24));
            }

            Log::info('SQL query executed successfully', [
                'database_id' => $this->databaseId,
                'rows' => count($result['data'] ?? []),
            ]);
        } catch (\Exception $e) {
            Log::error('SQL query execution failed', [
                'database_id' => $this->databaseId,
                'error' => $e->getMessage(),
            ]);

            $result = [
                'status' => 'failed',
                'error' => $e->getMessage(),
                'executed_at' => now()->toIso8601String(),
            ];

            if ($this->resultKey) {
                Cache::put($this->resultKey, $result, now()->addHours(24));
            }

            throw $e;
        }
    }

    public function failed(\Throwable $exception): void
    {
        Log::error('Query execution job failed permanently', [
            'database_id' => $this->databaseId,
            'error' => $exception->getMessage(),
        ]);
    }
}
