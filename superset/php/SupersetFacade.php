<?php

declare(strict_types=1);

namespace App\Services\Superset;

use Illuminate\Support\Facades\Facade;

/**
 * Superset Facade
 *
 * @method static self authenticate()
 * @method static array getCurrentUser()
 * @method static array getDashboards(int $page = 0, int $pageSize = 25, array $filters = [])
 * @method static array getDashboard(int $id)
 * @method static array createDashboard(array $data)
 * @method static array updateDashboard(int $id, array $data)
 * @method static array deleteDashboard(int $id)
 * @method static string exportDashboards(array $ids)
 * @method static array getCharts(int $page = 0, int $pageSize = 25, array $filters = [])
 * @method static array getChart(int $id)
 * @method static array getChartData(int $chartId, array $queryContext = [])
 * @method static array getDatasets(int $page = 0, int $pageSize = 25, array $filters = [])
 * @method static array getDataset(int $id)
 * @method static array createDataset(array $data)
 * @method static array updateDataset(int $id, array $data)
 * @method static array refreshDataset(int $id)
 * @method static array getDatabases(int $page = 0, int $pageSize = 25)
 * @method static array getDatabase(int $id)
 * @method static array createDatabase(array $data)
 * @method static array testDatabaseConnection(array $data)
 * @method static array getDatabaseSchemas(int $databaseId)
 * @method static array getDatabaseTables(int $databaseId, string $schema)
 * @method static array executeSql(int $databaseId, string $sql, ?string $schema = null, int $limit = 1000, bool $async = false)
 * @method static array getQueryResults(string $queryId)
 * @method static array enableDashboardEmbedding(int $dashboardId, array $allowedDomains = [])
 * @method static array disableDashboardEmbedding(int $dashboardId)
 * @method static array getDashboardEmbedded(int $dashboardId)
 * @method static array createGuestToken(array $resources, array $user = [], array $rls = [])
 * @method static string getEmbedUrl(int $dashboardId, bool $standalone = true, bool $showFilters = true)
 * @method static array getReports(int $page = 0, int $pageSize = 25)
 * @method static array createReport(array $data)
 * @method static array updateReport(int $id, array $data)
 * @method static array deleteReport(int $id)
 * @method static array getRoles(int $page = 0, int $pageSize = 25)
 * @method static array getUsers(int $page = 0, int $pageSize = 25)
 *
 * @see \App\Services\Superset\SupersetClient
 */
class Superset extends Facade
{
    /**
     * Get the registered name of the component.
     */
    protected static function getFacadeAccessor(): string
    {
        return SupersetClient::class;
    }
}
