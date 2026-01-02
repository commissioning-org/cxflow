<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\Superset\SupersetClient;
use Illuminate\Console\Command;

/**
 * Superset SQL Lab Query Command
 *
 * Provides CLI interface for executing SQL queries via Superset SQL Lab.
 */
final class SupersetQuery extends Command
{
    protected $signature = 'superset:query
        {action : Action to perform: execute, results, list-databases}
        {--database= : Database ID}
        {--sql= : SQL query to execute}
        {--schema= : Database schema}
        {--limit=1000 : Query result limit}
        {--async : Execute query asynchronously}
        {--query-id= : Query ID for fetching results}
        {--json : Output as JSON}
        {--output= : Output file for results}
    ';

    protected $description = 'Execute SQL queries via Superset SQL Lab';

    public function handle(SupersetClient $client): int
    {
        $action = (string) $this->argument('action');

        try {
            $client->authenticate();

            return match ($action) {
                'execute' => $this->executeQuery($client),
                'results' => $this->getResults($client),
                'list-databases' => $this->listDatabases($client),
                default => $this->error("Unknown action: {$action}") ?: self::FAILURE,
            };
        } catch (\Exception $e) {
            $this->error("Error: {$e->getMessage()}");
            return self::FAILURE;
        }
    }

    private function executeQuery(SupersetClient $client): int
    {
        $databaseId = (int) $this->option('database');
        $sql = (string) $this->option('sql');

        if (!$databaseId || !$sql) {
            $this->error('Both --database and --sql are required');
            return self::FAILURE;
        }

        $schema = $this->option('schema') ? (string) $this->option('schema') : null;
        $limit = (int) $this->option('limit');
        $async = (bool) $this->option('async');

        $result = $client->executeSql($databaseId, $sql, $schema, $limit, $async);

        if ($this->option('json')) {
            $this->line(json_encode($result, JSON_PRETTY_PRINT));
            return self::SUCCESS;
        }

        if ($async) {
            $queryId = $result['query_id'] ?? 'N/A';
            $this->info("Query submitted asynchronously");
            $this->line("Query ID: {$queryId}");
            $this->line("Use: superset:query results --query-id={$queryId}");
        } else {
            $this->displayResults($result);
        }

        return self::SUCCESS;
    }

    private function getResults(SupersetClient $client): int
    {
        $queryId = (string) $this->option('query-id');
        if (!$queryId) {
            $this->error('Query ID is required (--query-id)');
            return self::FAILURE;
        }

        $result = $client->getQueryResults($queryId);

        if ($this->option('json')) {
            $this->line(json_encode($result, JSON_PRETTY_PRINT));
            return self::SUCCESS;
        }

        $this->displayResults($result);

        return self::SUCCESS;
    }

    private function displayResults(array $result): void
    {
        $status = $result['status'] ?? 'unknown';
        $this->info("Query Status: {$status}");

        if ($status === 'success') {
            $data = $result['data'] ?? [];
            $columns = $result['columns'] ?? [];

            if (empty($data)) {
                $this->line('No results returned.');
                return;
            }

            if ($output = $this->option('output')) {
                file_put_contents($output, json_encode($result, JSON_PRETTY_PRINT));
                $this->info("Results saved to {$output}");
                return;
            }

            $headers = array_column($columns, 'name');
            $rows = array_map(fn($row) => array_values((array) $row), $data);

            $this->table($headers, array_slice($rows, 0, 50));

            if (count($data) > 50) {
                $this->line('... (showing first 50 rows of ' . count($data) . ')');
            }
        } elseif ($status === 'failed') {
            $error = $result['error'] ?? 'Unknown error';
            $this->error("Query failed: {$error}");
        } else {
            $this->line('Query is still running...');
        }
    }

    private function listDatabases(SupersetClient $client): int
    {
        $result = $client->getDatabases();

        if ($this->option('json')) {
            $this->line(json_encode($result, JSON_PRETTY_PRINT));
            return self::SUCCESS;
        }

        $databases = $result['result'] ?? [];
        $count = $result['count'] ?? 0;

        $this->info("Found {$count} databases:");
        $this->table(
            ['ID', 'Name', 'Backend', 'Created'],
            array_map(fn($d) => [
                $d['id'] ?? '',
                $d['database_name'] ?? '',
                $d['backend'] ?? '',
                $d['created_on'] ?? '',
            ], $databases)
        );

        return self::SUCCESS;
    }
}
