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
use Illuminate\Support\Facades\Storage;

/**
 * Export Dashboard Job
 *
 * Asynchronously exports Superset dashboards.
 */
final class ExportDashboard implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $timeout = 300;
    public int $tries = 3;

    /**
     * @param array<int> $dashboardIds
     */
    public function __construct(
        private readonly array $dashboardIds,
        private readonly string $outputPath,
        private readonly ?string $resultKey = null
    ) {
    }

    public function handle(SupersetClient $client): void
    {
        try {
            Log::info('Starting dashboard export', [
                'dashboard_ids' => $this->dashboardIds,
                'output_path' => $this->outputPath,
            ]);

            $client->authenticate();
            $zipContent = $client->exportDashboards($this->dashboardIds);

            // Save to storage
            Storage::put($this->outputPath, $zipContent);

            $result = [
                'status' => 'success',
                'dashboard_ids' => $this->dashboardIds,
                'output_path' => $this->outputPath,
                'size' => strlen($zipContent),
                'exported_at' => now()->toIso8601String(),
            ];

            if ($this->resultKey) {
                Cache::put($this->resultKey, $result, now()->addHours(24));
            }

            Log::info('Dashboard export completed', $result);
        } catch (\Exception $e) {
            Log::error('Dashboard export failed', [
                'dashboard_ids' => $this->dashboardIds,
                'error' => $e->getMessage(),
            ]);

            $result = [
                'status' => 'failed',
                'dashboard_ids' => $this->dashboardIds,
                'error' => $e->getMessage(),
            ];

            if ($this->resultKey) {
                Cache::put($this->resultKey, $result, now()->addHours(24));
            }

            throw $e;
        }
    }

    public function failed(\Throwable $exception): void
    {
        Log::error('Dashboard export job failed permanently', [
            'dashboard_ids' => $this->dashboardIds,
            'error' => $exception->getMessage(),
        ]);
    }
}
