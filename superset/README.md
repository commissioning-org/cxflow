# Apache Superset Integration Package

A comprehensive Python and PHP integration package for Apache Superset, providing:

- 🐍 **Python Client Library** - Full REST API client with sync and async support
- 🐘 **PHP/Laravel Integration** - Service provider, facade, and HTTP client
- 🐳 **Docker Configuration** - Production-ready Docker Compose setup
- 🔧 **CLI Tools** - Command-line interface for Superset operations

## Features

### Python Client
- Full Superset REST API coverage
- Synchronous and asynchronous clients
- Dashboard, Chart, Dataset, Database management
- SQL Lab query execution
- User and role management
- Row-level security
- Report scheduling
- Dashboard embedding with guest tokens

### PHP/Laravel
- Laravel service provider and facade
- HTTP client with authentication caching
- Guest token generation for embedding
- All major API endpoints
- **Artisan Console Commands** - CLI for dashboard, query, and sync operations
- **Queue Jobs** - Async export, query execution, and sync
- **Eloquent Models** - Local caching of dashboards, charts, and datasets
- **Query Builder** - Fluent interface for building complex queries
- **Embed Helper** - Utilities for dashboard embedding with RLS
- **Webhook Notifier** - Event notifications for Superset operations
- **Bulk Operations** - Batch delete and manage resources
- **Retry Logic** - Automatic retry with exponential backoff
- **Database Migrations** - Track and sync Superset resources locally

### Docker
- Production-ready Docker Compose
- PostgreSQL and Redis for metadata/caching
- Celery workers for async tasks
- Configurable via environment variables

## Installation

### Python

```bash
# Install the package
pip install -e ./superset

# Or install with async support
pip install -e ./superset[async]
```

### PHP/Laravel

1. Copy the PHP files to your Laravel project:
```bash
cp -r superset/php/* app/Services/Superset/
```

2. Register the service provider in `config/app.php`:
```php
'providers' => [
    // ...
    App\Services\Superset\SupersetServiceProvider::class,
],

'aliases' => [
    // ...
    'Superset' => App\Services\Superset\SupersetFacade::class,
],
```

3. Publish the configuration:
```bash
php artisan vendor:publish --tag=superset-config
```

4. Configure environment variables:
```env
SUPERSET_URL=http://localhost:8088
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=admin
```

### Docker

```bash
cd superset/docker

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# Start Superset
docker-compose up -d

# Initialize (first time only)
docker-compose up superset-init
```

## Usage

### Python

```python
from superset import SupersetClient, SupersetConfig
from superset.dashboards import DashboardManager
from superset.sql_lab import SQLLabClient

# Create client
config = SupersetConfig(
    base_url="http://localhost:8088",
    username="admin",
    password="admin",
)
client = SupersetClient(config)

# Dashboard operations
dashboard_manager = DashboardManager(client)

# List dashboards
dashboards = dashboard_manager.list_dashboards()
for dashboard in dashboards:
    print(f"{dashboard.id}: {dashboard.title}")

# Create dashboard
new_dashboard = dashboard_manager.create_dashboard(
    title="Sales Overview",
    published=True,
)

# SQL Lab
sql = SQLLabClient(client)

# Execute query
result = sql.execute(
    database_id=1,
    sql="SELECT * FROM sales LIMIT 10",
)

for row in result:
    print(row)

# Convert to DataFrame
df = result.to_dataframe()
```

### Async Python

```python
import asyncio
from superset import AsyncSupersetClient, SupersetConfig

async def main():
    config = SupersetConfig(
        base_url="http://localhost:8088",
        username="admin",
        password="admin",
    )
    
    async with AsyncSupersetClient(config) as client:
        # Get dashboards
        result = await client.get_dashboards()
        print(result)

asyncio.run(main())
```

### PHP/Laravel

```php
use App\Services\Superset\Superset;

// List dashboards
$dashboards = Superset::getDashboards();

// Execute SQL
$result = Superset::executeSql(
    databaseId: 1,
    sql: "SELECT * FROM users LIMIT 10"
);

// Generate embed URL
$url = Superset::getEmbedUrl(dashboardId: 1);

// Create guest token for embedding
$token = Superset::createGuestToken(
    resources: [['type' => 'dashboard', 'id' => '1']],
    user: ['username' => 'guest_user'],
);
```

### CLI

```bash
# List dashboards
python superset/cli/superset_cli.py dashboard list

# Execute query
python superset/cli/superset_cli.py query execute 1 "SELECT * FROM users"

# Export dashboard
python superset/cli/superset_cli.py dashboard export 1 --output sales.zip

# Test database connection
python superset/cli/superset_cli.py database test 1
```

## Package Structure

```
superset/
├── __init__.py           # Package exports
├── config.py             # Configuration classes
├── client.py             # REST API clients (sync + async)
├── dashboards.py         # Dashboard management
├── datasets.py           # Dataset management
├── databases.py          # Database management
├── security.py           # Security/RBAC management
├── embedding.py          # Dashboard embedding
├── reports.py            # Report scheduling
├── sql_lab.py            # SQL Lab client
├── requirements.txt      # Python dependencies
├── php/                  # PHP/Laravel integration
│   ├── SupersetClient.php
│   ├── SupersetServiceProvider.php
│   ├── SupersetFacade.php
│   └── config/
│       └── superset.php
├── docker/               # Docker configuration
│   ├── docker-compose.yml
│   ├── superset_config.py
│   └── .env.example
└── cli/                  # CLI tools
    └── superset_cli.py
```

## Configuration

### Python

```python
from superset import SupersetConfig

config = SupersetConfig(
    base_url="https://superset.example.com",
    username="admin",
    password="secret",
    # Or use API key
    api_key="your-api-key",
    # Or OAuth2
    oauth2_client_id="client-id",
    oauth2_client_secret="client-secret",
    oauth2_token_url="https://auth.example.com/token",
)
```

### Environment Variables

```bash
# Python
export SUPERSET_URL=http://localhost:8088
export SUPERSET_USERNAME=admin
export SUPERSET_PASSWORD=admin

# PHP/Laravel
SUPERSET_URL=http://localhost:8088
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=admin
SUPERSET_VERIFY_SSL=true
```

## Embedding Dashboards

### Generate Guest Token (Python)

```python
from superset import SupersetClient, SupersetConfig
from superset.embedding import EmbeddingManager, GuestTokenResource

client = SupersetClient(config)
embedding = EmbeddingManager(client)

# Enable embedding for dashboard
embedded = embedding.enable_embedding(
    dashboard_id=1,
    allowed_domains=["https://myapp.com"],
)

# Generate guest token
token = embedding.create_guest_token(
    resources=[
        GuestTokenResource(type="dashboard", id="1"),
    ],
    user={"username": "guest_user"},
    rls=[{"clause": "team_id = 123"}],  # Row-level security
)

# Get embed URL
url = embedding.get_embed_url(
    dashboard_id=1,
    standalone=True,
    show_filters=True,
)

# Generate iframe HTML
html = embedding.generate_iframe_html(
    dashboard_id=1,
    width="100%",
    height="800px",
)
```

### Embed in Laravel Blade

```php
@php
    $token = Superset::createGuestToken([
        ['type' => 'dashboard', 'id' => '1']
    ]);
    $url = Superset::getEmbedUrl(1);
@endphp

<iframe 
    src="{{ $url }}"
    width="100%"
    height="800"
    frameborder="0"
></iframe>

<script>
    // Use Superset Embedded SDK for better integration
    import { embedDashboard } from "@superset-ui/embedded-sdk";
    
    embedDashboard({
        id: "{{ $embeddedId }}",
        supersetDomain: "{{ config('superset.base_url') }}",
        mountPoint: document.getElementById("superset-container"),
        fetchGuestToken: async () => {
            const response = await fetch("/api/superset/guest-token");
            const { token } = await response.json();
            return token;
        },
    });
</script>
```

## Docker Deployment

### Quick Start

```bash
cd superset/docker
cp .env.example .env

# Generate secret key
echo "SUPERSET_SECRET_KEY=$(openssl rand -base64 42)" >> .env

# Start services
docker-compose up -d

# Wait for initialization
docker-compose logs -f superset-init

# Access Superset
open http://localhost:8088
```

### Production Configuration

1. Set a strong `SUPERSET_SECRET_KEY`
2. Configure proper PostgreSQL password
3. Set up SSL/TLS termination (nginx/traefik)
4. Configure CORS for embedding
5. Set up SMTP for reports
6. Configure Slack integration if needed

## API Reference

See the docstrings in each module for detailed API documentation:

- [client.py](client.py) - Low-level API client
- [dashboards.py](dashboards.py) - Dashboard operations
- [datasets.py](datasets.py) - Dataset operations
- [databases.py](databases.py) - Database connections
- [security.py](security.py) - Users, roles, permissions
- [embedding.py](embedding.py) - Dashboard embedding
- [reports.py](reports.py) - Scheduled reports
- [sql_lab.py](sql_lab.py) - SQL execution

## PHP/Laravel Advanced Features

### Artisan Console Commands

The PHP integration includes comprehensive Artisan commands for managing Superset resources:

#### Dashboard Management

```bash
# List dashboards
php artisan superset:dashboard list --page=0 --page-size=25

# Show dashboard details
php artisan superset:dashboard show --id=1 --json

# Create dashboard
php artisan superset:dashboard create --title="Sales Dashboard" --published

# Update dashboard
php artisan superset:dashboard update --id=1 --title="New Title"

# Delete dashboard
php artisan superset:dashboard delete --id=1

# Export dashboards
php artisan superset:dashboard export --id=1,2,3 --output=dashboards.zip

# Enable embedding
php artisan superset:dashboard embed --id=1 --domains=https://example.com
```

#### SQL Query Execution

```bash
# Execute SQL query
php artisan superset:query execute --database=1 --sql="SELECT * FROM users LIMIT 10"

# Execute async query
php artisan superset:query execute --database=1 --sql="SELECT * FROM large_table" --async

# Get query results
php artisan superset:query results --query-id=abc-123

# List databases
php artisan superset:query list-databases

# Save results to file
php artisan superset:query execute --database=1 --sql="SELECT * FROM users" --output=results.json
```

#### Resource Synchronization

```bash
# Sync all resources
php artisan superset:sync --resource=all

# Sync specific resource
php artisan superset:sync --resource=dashboards

# Full sync (vs incremental)
php artisan superset:sync --resource=all --full

# Async sync via queue
php artisan superset:sync --resource=all --async

# Generate sync report
php artisan superset:sync --resource=all --report
```

### Queue Jobs

Perform long-running operations asynchronously:

```php
use App\Jobs\ExportDashboard;
use App\Jobs\ExecuteQuery;
use App\Jobs\SyncSuperset;

// Export dashboards in background
ExportDashboard::dispatch([1, 2, 3], 'exports/dashboards.zip', 'result-key-123');

// Execute long-running query
ExecuteQuery::dispatch(1, 'SELECT * FROM large_table', null, 10000, 'query-result-123');

// Sync resources in background
SyncSuperset::dispatch('all', true, 'sync-result-123');

// Check job results
$result = Cache::get('result-key-123');
```

### Eloquent Models

Work with Superset resources using Laravel Eloquent:

```php
use App\Models\SupersetDashboard;
use App\Models\SupersetChart;
use App\Models\SupersetDataset;

// Query dashboards
$dashboards = SupersetDashboard::where('published', true)
    ->orderBy('created_at', 'desc')
    ->get();

// Get dashboard with charts
$dashboard = SupersetDashboard::where('dashboard_id', 1)->first();
$charts = $dashboard->charts();

// Get chart with dataset
$chart = SupersetChart::where('chart_id', 1)->first();
$dataset = $chart->dataset();

// Query by visualization type
$pieCharts = SupersetChart::where('viz_type', 'pie')->get();

// Get dataset columns
$dataset = SupersetDataset::where('dataset_id', 1)->first();
$columns = $dataset->getColumns();
$metrics = $dataset->getMetrics();
```

### Query Builder

Build complex Superset queries with a fluent interface:

```php
use App\Services\Superset\SupersetQueryBuilder;

// Build a query
$query = SupersetQueryBuilder::make(1)  // dataset ID
    ->columns(['country', 'region'])
    ->count('*', 'total_count')
    ->sum('revenue', 'total_revenue')
    ->avg('order_value', 'avg_order')
    ->where('status', '==', 'completed')
    ->whereIn('country', ['US', 'CA', 'UK'])
    ->timeColumn('created_at')
    ->last(30, 'days')
    ->groupBy(['country', 'region'])
    ->orderBy('total_revenue', false)
    ->limit(100)
    ->build();

// Use with SupersetClient
$client = app(SupersetClient::class);
$client->authenticate();
$result = $client->request('POST', '/api/v1/chart/data', $query);
```

### Embed Helper

Generate embedded dashboards with row-level security:

```php
use App\Services\Superset\SupersetEmbedHelper;
use App\Services\Superset\SupersetClient;

$client = app(SupersetClient::class);
$embedHelper = new SupersetEmbedHelper($client, config('superset.base_url'));

// Simple iframe embed
$html = $embedHelper->generateDashboardEmbed(
    dashboardId: 1,
    width: 100,
    widthUnit: '%',
    height: 800
);

// Embed with guest token and RLS
$package = $embedHelper->generateEmbedPackage(
    dashboardId: 1,
    rowLevelSecurity: ['team_id = 123', 'region = "US"'],
    user: ['username' => 'john.doe', 'first_name' => 'John', 'last_name' => 'Doe'],
    options: [
        'allowed_domains' => ['https://example.com'],
        'expiry_seconds' => 600,
        'width' => 100,
        'height' => 800,
    ]
);

// Use Superset Embedded SDK
$sdkCode = $embedHelper->generateEmbeddedSDKCode(
    dashboardId: 1,
    containerId: 'superset-container',
    fetchTokenUrl: '/api/superset/token'
);
```

### Webhook Notifier

Send notifications for Superset events:

```php
use App\Services\Superset\SupersetWebhookNotifier;

$notifier = SupersetWebhookNotifier::make('https://hooks.example.com/superset');

// Notify about dashboard events
$notifier->notifyDashboardCreated($dashboard);
$notifier->notifyDashboardUpdated($dashboard);
$notifier->notifyDashboardDeleted(1);

// Notify about query execution
$notifier->notifyQueryExecuted($queryResult);

// Notify about sync completion
$notifier->notifySyncCompleted($stats);

// Custom event notification
$notifier->notifyEvent('custom.event', ['key' => 'value']);
```

### Bulk Operations

Perform batch operations on multiple resources:

```php
use App\Services\Superset\SupersetClient;

$client = app(SupersetClient::class);
$client->authenticate();

// Bulk delete dashboards
$client->bulkDeleteDashboards([1, 2, 3, 4, 5]);

// Bulk delete charts
$client->bulkDeleteCharts([10, 11, 12]);

// Bulk delete datasets
$client->bulkDeleteDatasets([20, 21, 22]);

// Duplicate dashboard
$newDashboard = $client->duplicateDashboard(1, 'Copy of Sales Dashboard');

// Favorite/unfavorite
$client->favoriteDashboard(1);
$client->unfavoriteDashboard(1);
```

### Advanced Client Features

```php
use App\Services\Superset\SupersetClient;

$client = app(SupersetClient::class);
$client->authenticate();

// Health check
$health = $client->health();

// Version info
$version = $client->version();

// Get dashboard filters
$filters = $client->getDashboardFilters(1);

// Get chart SQL
$sql = $client->getChartSql(1);

// Validate SQL
$validation = $client->validateSql(1, 'SELECT * FROM users');

// Get query history
$history = $client->getQueryHistory();

// Get available database drivers
$drivers = $client->getAvailableDatabaseDrivers();

// Import dashboards
$zipContent = file_get_contents('dashboards.zip');
$client->importDashboards($zipContent, overwrite: false);
```

### Database Migrations

Run migrations to set up local tracking tables:

```bash
# Copy migrations to your Laravel project
cp superset/php/database/migrations/* database/migrations/

# Run migrations
php artisan migrate

# This creates:
# - superset_dashboards
# - superset_charts
# - superset_datasets
# - superset_sync_history
```

### Configuration

Enhanced configuration options in `config/superset.php`:

```php
return [
    'base_url' => env('SUPERSET_URL', 'http://localhost:8088'),
    'username' => env('SUPERSET_USERNAME', 'admin'),
    'password' => env('SUPERSET_PASSWORD', 'admin'),
    'verify_ssl' => env('SUPERSET_VERIFY_SSL', true),
    'token_cache_duration' => env('SUPERSET_TOKEN_CACHE', 30),
    
    'query' => [
        'limit' => env('SUPERSET_QUERY_LIMIT', 1000),
        'timeout' => env('SUPERSET_QUERY_TIMEOUT', 300),
    ],
    
    'embedding' => [
        'allowed_domains' => array_filter(explode(',', env('SUPERSET_ALLOWED_DOMAINS', ''))),
        'guest_token_expiry' => env('SUPERSET_GUEST_TOKEN_EXPIRY', 300),
    ],
    
    'webhook' => [
        'url' => env('SUPERSET_WEBHOOK_URL'),
        'enabled' => env('SUPERSET_WEBHOOK_ENABLED', false),
        'timeout' => env('SUPERSET_WEBHOOK_TIMEOUT', 10),
        'retries' => env('SUPERSET_WEBHOOK_RETRIES', 3),
    ],
    
    'sync' => [
        'enabled' => env('SUPERSET_SYNC_ENABLED', true),
        'schedule' => env('SUPERSET_SYNC_SCHEDULE', 'hourly'),
        'full_sync_on_startup' => env('SUPERSET_FULL_SYNC_ON_STARTUP', false),
    ],
    
    'retry' => [
        'max_attempts' => env('SUPERSET_RETRY_MAX_ATTEMPTS', 3),
        'backoff_multiplier' => env('SUPERSET_RETRY_BACKOFF', 2),
    ],
    
    'rate_limit' => [
        'enabled' => env('SUPERSET_RATE_LIMIT_ENABLED', false),
        'max_requests' => env('SUPERSET_RATE_LIMIT_MAX', 100),
        'per_minutes' => env('SUPERSET_RATE_LIMIT_MINUTES', 1),
    ],
];
```

### Environment Variables

```env
# Basic Configuration
SUPERSET_URL=http://localhost:8088
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=admin
SUPERSET_VERIFY_SSL=true

# Token Caching
SUPERSET_TOKEN_CACHE=30

# Query Settings
SUPERSET_QUERY_LIMIT=1000
SUPERSET_QUERY_TIMEOUT=300

# Embedding
SUPERSET_ALLOWED_DOMAINS=https://app.example.com,https://dashboard.example.com
SUPERSET_GUEST_TOKEN_EXPIRY=300

# Webhooks
SUPERSET_WEBHOOK_URL=https://hooks.example.com/superset
SUPERSET_WEBHOOK_ENABLED=true
SUPERSET_WEBHOOK_TIMEOUT=10
SUPERSET_WEBHOOK_RETRIES=3

# Sync Settings
SUPERSET_SYNC_ENABLED=true
SUPERSET_SYNC_SCHEDULE=hourly
SUPERSET_FULL_SYNC_ON_STARTUP=false

# Retry Configuration
SUPERSET_RETRY_MAX_ATTEMPTS=3
SUPERSET_RETRY_BACKOFF=2

# Rate Limiting
SUPERSET_RATE_LIMIT_ENABLED=false
SUPERSET_RATE_LIMIT_MAX=100
SUPERSET_RATE_LIMIT_MINUTES=1
```

## License

MIT License - See LICENSE file for details.
