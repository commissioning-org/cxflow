<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Jobs\SyncSuperset;
use App\Services\Superset\SupersetClient;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Superset Sync Command
 *
 * Synchronizes Superset resources with local database:
 * - Sync dashboards, charts, datasets
 * - Track changes and updates
 * - Generate sync reports
 */
final class SupersetSync extends Command
{
    protected $signature = 'superset:sync
        {--resource=all : Resource type: all, dashboards, charts, datasets}
        {--full : Perform full sync (otherwise incremental)}
        {--async : Run sync asynchronously via queue}
        {--report : Generate sync report}
    ';

    protected $description = 'Sync Superset resources to local database';

    public function handle(SupersetClient $client): int
    {
        $resource = (string) $this->option('resource');
        $full = (bool) $this->option('full');
        $async = (bool) $this->option('async');

        if ($async) {
            return $this->runAsync($resource, $full);
        }

        try {
            $client->authenticate();

            $syncType = $full ? 'full' : 'incremental';
            $this->info("Starting {$syncType} sync for: {$resource}");

            $stats = $this->performSync($client, $resource, $full);

            if ($this->option('report')) {
                $this->generateReport($stats);
            }

            $this->info('Sync completed successfully!');
            $this->displayStats($stats);

            return self::SUCCESS;
        } catch (\Exception $e) {
            $this->error("Sync failed: {$e->getMessage()}");
            return self::FAILURE;
        }
    }

    private function runAsync(string $resource, bool $full): int
    {
        $resultKey = 'superset:sync:' . Str::uuid();
        Cache::put($resultKey, ['status' => 'pending'], now()->addMinutes(30));

        SyncSuperset::dispatch($resource, $full, $resultKey);

        $this->info("Sync job dispatched");
        $this->line("Track with key: {$resultKey}");

        return self::SUCCESS;
    }

    private function performSync(SupersetClient $client, string $resource, bool $full): array
    {
        $stats = [
            'dashboards' => ['synced' => 0, 'created' => 0, 'updated' => 0],
            'charts' => ['synced' => 0, 'created' => 0, 'updated' => 0],
            'datasets' => ['synced' => 0, 'created' => 0, 'updated' => 0],
            'started_at' => now()->toIso8601String(),
        ];

        if ($resource === 'all' || $resource === 'dashboards') {
            $this->line('Syncing dashboards...');
            $stats['dashboards'] = $this->syncDashboards($client, $full);
        }

        if ($resource === 'all' || $resource === 'charts') {
            $this->line('Syncing charts...');
            $stats['charts'] = $this->syncCharts($client, $full);
        }

        if ($resource === 'all' || $resource === 'datasets') {
            $this->line('Syncing datasets...');
            $stats['datasets'] = $this->syncDatasets($client, $full);
        }

        $stats['finished_at'] = now()->toIso8601String();

        return $stats;
    }

    private function syncDashboards(SupersetClient $client, bool $full): array
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

                // Check if dashboard exists in local DB
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

    private function syncCharts(SupersetClient $client, bool $full): array
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

    private function syncDatasets(SupersetClient $client, bool $full): array
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

    private function displayStats(array $stats): void
    {
        $this->newLine();
        $this->line('Sync Statistics:');
        $this->table(
            ['Resource', 'Synced', 'Created', 'Updated'],
            [
                ['Dashboards', $stats['dashboards']['synced'], $stats['dashboards']['created'], $stats['dashboards']['updated']],
                ['Charts', $stats['charts']['synced'], $stats['charts']['created'], $stats['charts']['updated']],
                ['Datasets', $stats['datasets']['synced'], $stats['datasets']['created'], $stats['datasets']['updated']],
            ]
        );
    }

    private function generateReport(array $stats): void
    {
        $report = [
            'sync_type' => 'superset_sync',
            'timestamp' => now()->toIso8601String(),
            'stats' => $stats,
        ];

        $filename = 'superset-sync-' . now()->format('Y-m-d-His') . '.json';
        file_put_contents(storage_path("logs/{$filename}"), json_encode($report, JSON_PRETTY_PRINT));

        $this->info("Report saved to: storage/logs/{$filename}");
    }
}
