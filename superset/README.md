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

## License

MIT License - See LICENSE file for details.
