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
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * Sync Superset Job
 *
 * Synchronizes Superset resources to local database.
 */
final class SyncSuperset implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $timeout = 1800;
    public int $tries = 1;

    public function __construct(
        private readonly string $resource = 'all',
        private readonly bool $full = false,
        private readonly ?string $resultKey = null
    ) {
    }

    public function handle(SupersetClient $client): void
    {
        try {
            Log::info('Starting Superset sync', [
                'resource' => $this->resource,
                'full' => $this->full,
            ]);

            $client->authenticate();

            $stats = [
                'dashboards' => ['synced' => 0, 'created' => 0, 'updated' => 0],
                'charts' => ['synced' => 0, 'created' => 0, 'updated' => 0],
                'datasets' => ['synced' => 0, 'created' => 0, 'updated' => 0],
                'started_at' => now()->toIso8601String(),
            ];

            if ($this->resource === 'all' || $this->resource === 'dashboards') {
                $stats['dashboards'] = $this->syncDashboards($client);
            }

            if ($this->resource === 'all' || $this->resource === 'charts') {
                $stats['charts'] = $this->syncCharts($client);
            }

            if ($this->resource === 'all' || $this->resource === 'datasets') {
                $stats['datasets'] = $this->syncDatasets($client);
            }

            $stats['finished_at'] = now()->toIso8601String();
            $stats['status'] = 'success';

            if ($this->resultKey) {
                Cache::put($this->resultKey, $stats, now()->addHours(24));
            }

            Log::info('Superset sync completed', $stats);
        } catch (\Exception $e) {
            Log::error('Superset sync failed', [
                'resource' => $this->resource,
                'error' => $e->getMessage(),
            ]);

            $result = [
                'status' => 'failed',
                'resource' => $this->resource,
                'error' => $e->getMessage(),
            ];

            if ($this->resultKey) {
                Cache::put($this->resultKey, $result, now()->addHours(24));
            }

            throw $e;
        }
    }

    /**
     * @return array{synced: int, created: int, updated: int}
     */
    private function syncDashboards(SupersetClient $client): array
    {
        $stats = ['synced' => 0, 'created' => 0, 'updated' => 0];
        $page = 0;
        $pageSize = 50;

        do {
            $result = $client->getDashboards($page, $pageSize);
            $dashboards = $result['result'] ?? [];

            foreach ($dashboards as $dashboard) {
                $id = $dashboard['id'] ?? null;
                if (!$id) continue;

                $existing = DB::table('superset_dashboards')
                    ->where('dashboard_id', $id)
                    ->first();

                if ($existing) {
                    DB::table('superset_dashboards')
                        ->where('dashboard_id', $id)
                        ->update([
                            'title' => $dashboard['dashboard_title'] ?? '',
                            'slug' => $dashboard['slug'] ?? '',
                            'published' => $dashboard['published'] ?? false,
                            'data' => json_encode($dashboard),
                            'updated_at' => now(),
                        ]);
                    $stats['updated']++;
                } else {
                    DB::table('superset_dashboards')->insert([
                        'dashboard_id' => $id,
                        'title' => $dashboard['dashboard_title'] ?? '',
                        'slug' => $dashboard['slug'] ?? '',
                        'published' => $dashboard['published'] ?? false,
                        'data' => json_encode($dashboard),
                        'created_at' => now(),
                        'updated_at' => now(),
                    ]);
                    $stats['created']++;
                }

                $stats['synced']++;
            }

            $page++;
        } while (count($dashboards) === $pageSize);

        return $stats;
    }

    /**
     * @return array{synced: int, created: int, updated: int}
     */
    private function syncCharts(SupersetClient $client): array
    {
        $stats = ['synced' => 0, 'created' => 0, 'updated' => 0];
        $page = 0;
        $pageSize = 50;

        do {
            $result = $client->getCharts($page, $pageSize);
            $charts = $result['result'] ?? [];

            foreach ($charts as $chart) {
                $id = $chart['id'] ?? null;
                if (!$id) continue;

                $existing = DB::table('superset_charts')
                    ->where('chart_id', $id)
                    ->first();

                if ($existing) {
                    DB::table('superset_charts')
                        ->where('chart_id', $id)
                        ->update([
                            'name' => $chart['slice_name'] ?? '',
                            'viz_type' => $chart['viz_type'] ?? '',
                            'data' => json_encode($chart),
                            'updated_at' => now(),
                        ]);
                    $stats['updated']++;
                } else {
                    DB::table('superset_charts')->insert([
                        'chart_id' => $id,
                        'name' => $chart['slice_name'] ?? '',
                        'viz_type' => $chart['viz_type'] ?? '',
                        'data' => json_encode($chart),
                        'created_at' => now(),
                        'updated_at' => now(),
                    ]);
                    $stats['created']++;
                }

                $stats['synced']++;
            }

            $page++;
        } while (count($charts) === $pageSize);

        return $stats;
    }

    /**
     * @return array{synced: int, created: int, updated: int}
     */
    private function syncDatasets(SupersetClient $client): array
    {
        $stats = ['synced' => 0, 'created' => 0, 'updated' => 0];
        $page = 0;
        $pageSize = 50;

        do {
            $result = $client->getDatasets($page, $pageSize);
            $datasets = $result['result'] ?? [];

            foreach ($datasets as $dataset) {
                $id = $dataset['id'] ?? null;
                if (!$id) continue;

                $existing = DB::table('superset_datasets')
                    ->where('dataset_id', $id)
                    ->first();

                if ($existing) {
                    DB::table('superset_datasets')
                        ->where('dataset_id', $id)
                        ->update([
                            'name' => $dataset['table_name'] ?? '',
                            'schema' => $dataset['schema'] ?? '',
                            'data' => json_encode($dataset),
                            'updated_at' => now(),
                        ]);
                    $stats['updated']++;
                } else {
                    DB::table('superset_datasets')->insert([
                        'dataset_id' => $id,
                        'name' => $dataset['table_name'] ?? '',
                        'schema' => $dataset['schema'] ?? '',
                        'data' => json_encode($dataset),
                        'created_at' => now(),
                        'updated_at' => now(),
                    ]);
                    $stats['created']++;
                }

                $stats['synced']++;
            }

            $page++;
        } while (count($datasets) === $pageSize);

        return $stats;
    }

    public function failed(\Throwable $exception): void
    {
        Log::error('Superset sync job failed permanently', [
            'resource' => $this->resource,
            'error' => $exception->getMessage(),
        ]);
    }
}
