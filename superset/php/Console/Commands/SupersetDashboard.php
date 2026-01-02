<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\Superset\SupersetClient;
use Illuminate\Console\Command;

/**
 * Superset Dashboard Management Command
 *
 * Provides CLI interface for managing Superset dashboards:
 * - List, show, create, update, delete dashboards
 * - Export and import dashboards
 * - Enable/disable embedding
 */
final class SupersetDashboard extends Command
{
    protected $signature = 'superset:dashboard
        {action : Action to perform: list, show, create, update, delete, export, embed}
        {--id= : Dashboard ID}
        {--title= : Dashboard title}
        {--published : Mark dashboard as published}
        {--slug= : Dashboard slug}
        {--owners= : Comma-separated owner IDs}
        {--output= : Output file for export}
        {--domains= : Comma-separated allowed domains for embedding}
        {--page=0 : Page number for list}
        {--page-size=25 : Page size for list}
        {--json : Output as JSON}
    ';

    protected $description = 'Manage Superset dashboards';

    public function handle(SupersetClient $client): int
    {
        $action = (string) $this->argument('action');

        try {
            $client->authenticate();

            return match ($action) {
                'list' => $this->listDashboards($client),
                'show' => $this->showDashboard($client),
                'create' => $this->createDashboard($client),
                'update' => $this->updateDashboard($client),
                'delete' => $this->deleteDashboard($client),
                'export' => $this->exportDashboards($client),
                'embed' => $this->enableEmbedding($client),
                default => $this->error("Unknown action: {$action}") ?: self::FAILURE,
            };
        } catch (\Exception $e) {
            $this->error("Error: {$e->getMessage()}");
            return self::FAILURE;
        }
    }

    private function listDashboards(SupersetClient $client): int
    {
        $page = (int) $this->option('page');
        $pageSize = (int) $this->option('page-size');

        $result = $client->getDashboards($page, $pageSize);

        if ($this->option('json')) {
            $this->line(json_encode($result, JSON_PRETTY_PRINT));
            return self::SUCCESS;
        }

        $dashboards = $result['result'] ?? [];
        $count = $result['count'] ?? 0;

        $this->info("Found {$count} dashboards:");
        $this->table(
            ['ID', 'Title', 'Slug', 'Published', 'Owners'],
            array_map(fn($d) => [
                $d['id'] ?? '',
                $d['dashboard_title'] ?? '',
                $d['slug'] ?? '',
                ($d['published'] ?? false) ? 'Yes' : 'No',
                implode(', ', array_column($d['owners'] ?? [], 'username')),
            ], $dashboards)
        );

        return self::SUCCESS;
    }

    private function showDashboard(SupersetClient $client): int
    {
        $id = (int) $this->option('id');
        if (!$id) {
            $this->error('Dashboard ID is required (--id)');
            return self::FAILURE;
        }

        $dashboard = $client->getDashboard($id);

        if ($this->option('json')) {
            $this->line(json_encode($dashboard, JSON_PRETTY_PRINT));
            return self::SUCCESS;
        }

        $result = $dashboard['result'] ?? $dashboard;
        $this->info("Dashboard Details:");
        $this->line("ID: " . ($result['id'] ?? ''));
        $this->line("Title: " . ($result['dashboard_title'] ?? ''));
        $this->line("Slug: " . ($result['slug'] ?? ''));
        $this->line("Published: " . (($result['published'] ?? false) ? 'Yes' : 'No'));
        $this->line("Created: " . ($result['created_on'] ?? ''));
        $this->line("Modified: " . ($result['changed_on'] ?? ''));

        return self::SUCCESS;
    }

    private function createDashboard(SupersetClient $client): int
    {
        $title = (string) $this->option('title');
        if (!$title) {
            $this->error('Dashboard title is required (--title)');
            return self::FAILURE;
        }

        $data = [
            'dashboard_title' => $title,
            'published' => (bool) $this->option('published'),
        ];

        if ($slug = $this->option('slug')) {
            $data['slug'] = $slug;
        }

        if ($owners = $this->option('owners')) {
            $data['owners'] = array_map('intval', explode(',', $owners));
        }

        $result = $client->createDashboard($data);
        $this->info('Dashboard created successfully!');
        $this->line('ID: ' . ($result['id'] ?? 'N/A'));

        return self::SUCCESS;
    }

    private function updateDashboard(SupersetClient $client): int
    {
        $id = (int) $this->option('id');
        if (!$id) {
            $this->error('Dashboard ID is required (--id)');
            return self::FAILURE;
        }

        $data = [];

        if ($title = $this->option('title')) {
            $data['dashboard_title'] = $title;
        }

        if ($this->option('published') !== null) {
            $data['published'] = (bool) $this->option('published');
        }

        if ($slug = $this->option('slug')) {
            $data['slug'] = $slug;
        }

        if ($owners = $this->option('owners')) {
            $data['owners'] = array_map('intval', explode(',', $owners));
        }

        if (empty($data)) {
            $this->error('No update data provided');
            return self::FAILURE;
        }

        $client->updateDashboard($id, $data);
        $this->info("Dashboard {$id} updated successfully!");

        return self::SUCCESS;
    }

    private function deleteDashboard(SupersetClient $client): int
    {
        $id = (int) $this->option('id');
        if (!$id) {
            $this->error('Dashboard ID is required (--id)');
            return self::FAILURE;
        }

        if (!$this->confirm("Are you sure you want to delete dashboard {$id}?")) {
            $this->info('Cancelled.');
            return self::SUCCESS;
        }

        $client->deleteDashboard($id);
        $this->info("Dashboard {$id} deleted successfully!");

        return self::SUCCESS;
    }

    private function exportDashboards(SupersetClient $client): int
    {
        $ids = $this->option('id');
        if (!$ids) {
            $this->error('Dashboard ID(s) required (--id)');
            return self::FAILURE;
        }

        $idArray = array_map('intval', explode(',', $ids));
        $zipContent = $client->exportDashboards($idArray);

        $output = (string) ($this->option('output') ?: 'dashboards.zip');
        file_put_contents($output, $zipContent);

        $this->info("Exported " . count($idArray) . " dashboard(s) to {$output}");

        return self::SUCCESS;
    }

    private function enableEmbedding(SupersetClient $client): int
    {
        $id = (int) $this->option('id');
        if (!$id) {
            $this->error('Dashboard ID is required (--id)');
            return self::FAILURE;
        }

        $domains = [];
        if ($domainsStr = $this->option('domains')) {
            $domains = explode(',', $domainsStr);
        }

        $result = $client->enableDashboardEmbedding($id, $domains);
        $this->info("Embedding enabled for dashboard {$id}");
        $this->line('UUID: ' . ($result['result']['uuid'] ?? 'N/A'));

        return self::SUCCESS;
    }
}
