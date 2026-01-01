<?php

declare(strict_types=1);

namespace App\Services\Superset;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Illuminate\Http\Client\Response;
use Illuminate\Http\Client\PendingRequest;

/**
 * Apache Superset PHP Client
 *
 * Provides Laravel integration for Apache Superset:
 * - REST API client with authentication
 * - Guest token generation for embedding
 * - Dashboard and chart management
 * - SQL Lab query execution
 *
 * @package App\Services\Superset
 */
class SupersetClient
{
    protected string $baseUrl;
    protected string $username;
    protected string $password;
    protected ?string $accessToken = null;
    protected ?string $refreshToken = null;
    protected ?string $csrfToken = null;
    protected int $tokenExpiry = 0;

    /**
     * Create a new Superset client instance.
     */
    public function __construct(
        ?string $baseUrl = null,
        ?string $username = null,
        ?string $password = null
    ) {
        $this->baseUrl = rtrim($baseUrl ?? config('services.superset.base_url', 'http://localhost:8088'), '/');
        $this->username = $username ?? config('services.superset.username', 'admin');
        $this->password = $password ?? config('services.superset.password', 'admin');
    }

    /**
     * Get configured HTTP client.
     */
    protected function client(): PendingRequest
    {
        $client = Http::baseUrl($this->baseUrl)
            ->timeout(30)
            ->withOptions(['verify' => config('services.superset.verify_ssl', true)]);

        if ($this->accessToken) {
            $client->withToken($this->accessToken);
        }

        if ($this->csrfToken) {
            $client->withHeaders(['X-CSRFToken' => $this->csrfToken]);
        }

        return $client;
    }

    /**
     * Authenticate with Superset.
     */
    public function authenticate(): self
    {
        // Check cached token
        $cachedToken = Cache::get('superset_access_token');
        if ($cachedToken && Cache::get('superset_token_expiry', 0) > time()) {
            $this->accessToken = $cachedToken;
            $this->csrfToken = Cache::get('superset_csrf_token');
            return $this;
        }

        // Login
        $response = Http::baseUrl($this->baseUrl)
            ->post('/api/v1/security/login', [
                'username' => $this->username,
                'password' => $this->password,
                'provider' => 'db',
                'refresh' => true,
            ]);

        if (!$response->successful()) {
            throw new SupersetException('Authentication failed: ' . $response->body());
        }

        $data = $response->json();
        $this->accessToken = $data['access_token'];
        $this->refreshToken = $data['refresh_token'] ?? null;

        // Get CSRF token
        $this->csrfToken = $this->getCsrfToken();

        // Cache tokens
        Cache::put('superset_access_token', $this->accessToken, now()->addMinutes(30));
        Cache::put('superset_csrf_token', $this->csrfToken, now()->addMinutes(30));
        Cache::put('superset_token_expiry', time() + 1800, now()->addMinutes(30));

        return $this;
    }

    /**
     * Get CSRF token.
     */
    protected function getCsrfToken(): string
    {
        $response = $this->client()->get('/api/v1/security/csrf_token/');

        if ($response->successful()) {
            return $response->json('result', '');
        }

        return '';
    }

    /**
     * Ensure authenticated.
     */
    protected function ensureAuthenticated(): void
    {
        if (!$this->accessToken) {
            $this->authenticate();
        }
    }

    /**
     * Make API request.
     */
    protected function request(
        string $method,
        string $endpoint,
        array $data = [],
        array $query = []
    ): array {
        $this->ensureAuthenticated();

        $response = match (strtoupper($method)) {
            'GET' => $this->client()->get($endpoint, $query),
            'POST' => $this->client()->post($endpoint, $data),
            'PUT' => $this->client()->put($endpoint, $data),
            'DELETE' => $this->client()->delete($endpoint, $data),
            default => throw new \InvalidArgumentException("Invalid HTTP method: $method"),
        };

        if (!$response->successful()) {
            throw new SupersetException(
                "API request failed: {$response->status()} - {$response->body()}"
            );
        }

        return $response->json() ?? [];
    }

    /**
     * Get current user info.
     */
    public function getCurrentUser(): array
    {
        return $this->request('GET', '/api/v1/me/');
    }

    // =========================================================================
    // Dashboard Operations
    // =========================================================================

    /**
     * List dashboards.
     */
    public function getDashboards(
        int $page = 0,
        int $pageSize = 25,
        array $filters = []
    ): array {
        $query = [
            'q' => json_encode([
                'page' => $page,
                'page_size' => $pageSize,
                'filters' => $filters,
            ]),
        ];

        return $this->request('GET', '/api/v1/dashboard/', query: $query);
    }

    /**
     * Get dashboard by ID.
     */
    public function getDashboard(int $id): array
    {
        return $this->request('GET', "/api/v1/dashboard/{$id}");
    }

    /**
     * Create dashboard.
     */
    public function createDashboard(array $data): array
    {
        return $this->request('POST', '/api/v1/dashboard/', $data);
    }

    /**
     * Update dashboard.
     */
    public function updateDashboard(int $id, array $data): array
    {
        return $this->request('PUT', "/api/v1/dashboard/{$id}", $data);
    }

    /**
     * Delete dashboard.
     */
    public function deleteDashboard(int $id): array
    {
        return $this->request('DELETE', "/api/v1/dashboard/{$id}");
    }

    /**
     * Export dashboards.
     */
    public function exportDashboards(array $ids): string
    {
        $this->ensureAuthenticated();

        $response = $this->client()->get('/api/v1/dashboard/export/', [
            'q' => json_encode($ids),
        ]);

        if (!$response->successful()) {
            throw new SupersetException('Export failed: ' . $response->body());
        }

        return $response->body();
    }

    // =========================================================================
    // Chart Operations
    // =========================================================================

    /**
     * List charts.
     */
    public function getCharts(
        int $page = 0,
        int $pageSize = 25,
        array $filters = []
    ): array {
        $query = [
            'q' => json_encode([
                'page' => $page,
                'page_size' => $pageSize,
                'filters' => $filters,
            ]),
        ];

        return $this->request('GET', '/api/v1/chart/', query: $query);
    }

    /**
     * Get chart by ID.
     */
    public function getChart(int $id): array
    {
        return $this->request('GET', "/api/v1/chart/{$id}");
    }

    /**
     * Get chart data.
     */
    public function getChartData(int $chartId, array $queryContext = []): array
    {
        return $this->request('POST', '/api/v1/chart/data', [
            'datasource' => ['id' => $chartId, 'type' => 'table'],
            'queries' => [$queryContext],
        ]);
    }

    // =========================================================================
    // Dataset Operations
    // =========================================================================

    /**
     * List datasets.
     */
    public function getDatasets(
        int $page = 0,
        int $pageSize = 25,
        array $filters = []
    ): array {
        $query = [
            'q' => json_encode([
                'page' => $page,
                'page_size' => $pageSize,
                'filters' => $filters,
            ]),
        ];

        return $this->request('GET', '/api/v1/dataset/', query: $query);
    }

    /**
     * Get dataset by ID.
     */
    public function getDataset(int $id): array
    {
        return $this->request('GET', "/api/v1/dataset/{$id}");
    }

    /**
     * Create dataset.
     */
    public function createDataset(array $data): array
    {
        return $this->request('POST', '/api/v1/dataset/', $data);
    }

    /**
     * Update dataset.
     */
    public function updateDataset(int $id, array $data): array
    {
        return $this->request('PUT', "/api/v1/dataset/{$id}", $data);
    }

    /**
     * Refresh dataset columns.
     */
    public function refreshDataset(int $id): array
    {
        return $this->request('PUT', "/api/v1/dataset/{$id}/refresh");
    }

    // =========================================================================
    // Database Operations
    // =========================================================================

    /**
     * List databases.
     */
    public function getDatabases(int $page = 0, int $pageSize = 25): array
    {
        $query = [
            'q' => json_encode([
                'page' => $page,
                'page_size' => $pageSize,
            ]),
        ];

        return $this->request('GET', '/api/v1/database/', query: $query);
    }

    /**
     * Get database by ID.
     */
    public function getDatabase(int $id): array
    {
        return $this->request('GET', "/api/v1/database/{$id}");
    }

    /**
     * Create database connection.
     */
    public function createDatabase(array $data): array
    {
        return $this->request('POST', '/api/v1/database/', $data);
    }

    /**
     * Test database connection.
     */
    public function testDatabaseConnection(array $data): array
    {
        return $this->request('POST', '/api/v1/database/test_connection/', $data);
    }

    /**
     * Get database schemas.
     */
    public function getDatabaseSchemas(int $databaseId): array
    {
        return $this->request('GET', "/api/v1/database/{$databaseId}/schemas/");
    }

    /**
     * Get database tables.
     */
    public function getDatabaseTables(int $databaseId, string $schema): array
    {
        return $this->request('GET', "/api/v1/database/{$databaseId}/tables/", query: [
            'q' => json_encode(['schema_name' => $schema]),
        ]);
    }

    // =========================================================================
    // SQL Lab Operations
    // =========================================================================

    /**
     * Execute SQL query.
     */
    public function executeSql(
        int $databaseId,
        string $sql,
        ?string $schema = null,
        int $limit = 1000,
        bool $async = false
    ): array {
        return $this->request('POST', '/api/v1/sqllab/execute/', [
            'database_id' => $databaseId,
            'sql' => $sql,
            'schema' => $schema,
            'queryLimit' => $limit,
            'runAsync' => $async,
        ]);
    }

    /**
     * Get query results.
     */
    public function getQueryResults(string $queryId): array
    {
        return $this->request('GET', "/api/v1/sqllab/results/", query: [
            'key' => $queryId,
        ]);
    }

    // =========================================================================
    // Embedding Operations
    // =========================================================================

    /**
     * Enable dashboard embedding.
     */
    public function enableDashboardEmbedding(int $dashboardId, array $allowedDomains = []): array
    {
        return $this->request('POST', "/api/v1/dashboard/{$dashboardId}/embedded", [
            'allowed_domains' => $allowedDomains,
        ]);
    }

    /**
     * Disable dashboard embedding.
     */
    public function disableDashboardEmbedding(int $dashboardId): array
    {
        return $this->request('DELETE', "/api/v1/dashboard/{$dashboardId}/embedded");
    }

    /**
     * Get dashboard embedding configuration.
     */
    public function getDashboardEmbedded(int $dashboardId): array
    {
        return $this->request('GET', "/api/v1/dashboard/{$dashboardId}/embedded");
    }

    /**
     * Create guest token for embedding.
     */
    public function createGuestToken(array $resources, array $user = [], array $rls = []): array
    {
        return $this->request('POST', '/api/v1/security/guest_token/', [
            'resources' => $resources,
            'user' => $user,
            'rls' => $rls,
        ]);
    }

    /**
     * Generate embed URL for dashboard.
     */
    public function getEmbedUrl(
        int $dashboardId,
        bool $standalone = true,
        bool $showFilters = true
    ): string {
        $params = [];

        if ($standalone) {
            $mode = $showFilters ? 1 : 3;
            $params['standalone'] = $mode;
        }

        $url = "{$this->baseUrl}/superset/dashboard/{$dashboardId}/";

        if ($params) {
            $url .= '?' . http_build_query($params);
        }

        return $url;
    }

    // =========================================================================
    // Report Operations
    // =========================================================================

    /**
     * List reports.
     */
    public function getReports(int $page = 0, int $pageSize = 25): array
    {
        $query = [
            'q' => json_encode([
                'page' => $page,
                'page_size' => $pageSize,
            ]),
        ];

        return $this->request('GET', '/api/v1/report/', query: $query);
    }

    /**
     * Create report schedule.
     */
    public function createReport(array $data): array
    {
        return $this->request('POST', '/api/v1/report/', $data);
    }

    /**
     * Update report.
     */
    public function updateReport(int $id, array $data): array
    {
        return $this->request('PUT', "/api/v1/report/{$id}", $data);
    }

    /**
     * Delete report.
     */
    public function deleteReport(int $id): array
    {
        return $this->request('DELETE', "/api/v1/report/{$id}");
    }

    // =========================================================================
    // Security Operations
    // =========================================================================

    /**
     * List roles.
     */
    public function getRoles(int $page = 0, int $pageSize = 25): array
    {
        $query = [
            'q' => json_encode([
                'page' => $page,
                'page_size' => $pageSize,
            ]),
        ];

        return $this->request('GET', '/api/v1/security/roles/', query: $query);
    }

    /**
     * List users.
     */
    public function getUsers(int $page = 0, int $pageSize = 25): array
    {
        $query = [
            'q' => json_encode([
                'page' => $page,
                'page_size' => $pageSize,
            ]),
        ];

        return $this->request('GET', '/api/v1/security/users/', query: $query);
    }
}


/**
 * Superset Exception
 */
class SupersetException extends \Exception
{
}
