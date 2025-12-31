# Power BI Automation Integration

Comprehensive Power BI and Microsoft Fabric automation based on [marclelijveld/Power-BI-Automation](https://github.com/marclelijveld/Power-BI-Automation).

## Overview

This integration provides PHP and Python modules for automating Power BI and Microsoft Fabric operations:

- **Workspace Management**: Create, delete, configure workspaces
- **Deployment Pipelines**: Trigger CI/CD deployments
- **Dataset Operations**: Refresh, parameters, datasource updates
- **Dataflow Management**: List, migrate, transactions
- **XMLA Endpoints**: Backup, table refresh, role management
- **Fabric Operations**: Training workspaces, capacity management

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CXFlow Power BI Integration                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────┐     ┌────────────────────────┐                 │
│  │   PHP Module           │     │   Python SDK           │                 │
│  │   PowerBIAutomation.php│     │   powerbi_client.py    │                 │
│  └───────────┬────────────┘     └───────────┬────────────┘                 │
│              │                              │                               │
│              └──────────────┬───────────────┘                               │
│                             │                                               │
│                             ▼                                               │
│              ┌──────────────────────────────┐                              │
│              │      FastAPI Endpoints       │                              │
│              │      /powerbi/*              │                              │
│              │      /fabric/*               │                              │
│              └──────────────┬───────────────┘                              │
│                             │                                               │
│                             ▼                                               │
│              ┌──────────────────────────────┐                              │
│              │   Azure AD Authentication    │                              │
│              │   (Service Principal/User)   │                              │
│              └──────────────┬───────────────┘                              │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Power BI / Fabric APIs                         │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │ Workspaces  │ │  Datasets   │ │  Pipelines  │ │  Dataflows  │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Azure AD / Power BI Authentication
PBI_TENANT_ID=your-tenant-id
PBI_CLIENT_ID=your-client-id
PBI_CLIENT_SECRET=your-client-secret
PBI_AUTH_MODE=service_principal  # or 'user'

# User authentication (if PBI_AUTH_MODE=user)
PBI_USERNAME=user@domain.com
PBI_PASSWORD=your-password

# Optional settings
PBI_TIMEOUT=30
PBI_RETRY_COUNT=3

# Default targets (for orchestration integration)
PBI_WORKSPACE_ID=workspace-guid
PBI_DATASET_ID=dataset-guid
PBI_PIPELINE_ID=pipeline-guid
PBI_DEPLOY_STAGE=0
```

### Azure AD App Registration

1. Register an application in Azure AD
2. Add API permissions:
   - `Power BI Service` → `Tenant.ReadWrite.All` (for admin operations)
   - `Power BI Service` → `Dataset.ReadWrite.All`
   - `Power BI Service` → `Workspace.ReadWrite.All`
3. Grant admin consent
4. Create a client secret

## PHP Module Usage

### Basic Operations

```php
<?php
require_once 'powerbi/PowerBIAutomation.php';

use function CXFlow\PowerBI\{
    pbi_authenticate,
    pbi_list_workspaces,
    pbi_create_workspace,
    pbi_trigger_refresh,
    pbi_deploy_pipeline
};

// Authenticate
$auth = pbi_authenticate();
if (!$auth['success']) {
    die("Auth failed: " . $auth['error']);
}

// List workspaces
$workspaces = pbi_list_workspaces(top: 100);
foreach ($workspaces['workspaces'] as $ws) {
    echo "Workspace: {$ws['name']} ({$ws['id']})\n";
}

// Create workspace
$result = pbi_create_workspace('My New Workspace');
echo "Created: " . $result['workspace']['id'] . "\n";

// Trigger dataset refresh
$result = pbi_trigger_refresh(
    workspaceId: 'workspace-guid',
    datasetId: 'dataset-guid'
);

// Deploy pipeline (Dev → Test)
$result = pbi_deploy_pipeline(
    pipelineId: 'pipeline-guid',
    sourceStageOrder: 0,
    note: 'Automated deployment'
);
```

### DTAP Workspace Generation

```php
<?php
use function CXFlow\PowerBI\pbi_generate_dtap_workspaces;

// Generate Dev/Test/Prod workspaces
$result = pbi_generate_dtap_workspaces(
    baseName: 'Sales Analytics',
    capacityId: 'capacity-guid',
    stages: ['dev', 'tst', '']  // '' = production (no suffix)
);

// Result:
// - Sales Analytics-dev
// - Sales Analytics-tst
// - Sales Analytics (production)
```

### Dataflow Operations

```php
<?php
use function CXFlow\PowerBI\{
    pbi_list_dataflows,
    pbi_move_dataflow
};

// List dataflows
$dataflows = pbi_list_dataflows('workspace-id');

// Move dataflow with connection string replacement
$result = pbi_move_dataflow(
    sourceWorkspaceId: 'dev-workspace-id',
    destWorkspaceId: 'prod-workspace-id',
    dataflowId: 'dataflow-id',
    replacements: [
        'dev-storage.blob.core.windows.net' => 'prod-storage.blob.core.windows.net'
    ]
);
```

### XMLA Operations

```php
<?php
use function CXFlow\PowerBI\{
    pbi_get_xmla_endpoint,
    pbi_tmsl_backup,
    pbi_tmsl_refresh_table
};

// Get XMLA endpoint
$endpoint = pbi_get_xmla_endpoint('My Workspace');
// Result: powerbi://api.powerbi.com/v1.0/myorg/My%20Workspace

// Generate backup command
$tmsl = pbi_tmsl_backup(
    datasetName: 'Sales Model',
    backupFile: '20231215_Sales Model.abf'
);

// Generate table refresh command
$tmsl = pbi_tmsl_refresh_table(
    datasetName: 'Sales Model',
    tableName: 'FactSales'
);
```

## Python SDK Usage

### Async Client

```python
import asyncio
from powerbi.powerbi_client import PowerBIClient

async def main():
    async with PowerBIClient() as client:
        # List workspaces
        workspaces = await client.list_workspaces()
        for ws in workspaces:
            print(f"Workspace: {ws.name} ({ws.id})")
        
        # Trigger refresh
        await client.trigger_refresh(
            workspace_id="workspace-guid",
            dataset_id="dataset-guid"
        )
        
        # Deploy pipeline
        result = await client.deploy_pipeline(
            pipeline_id="pipeline-guid",
            source_stage=0,
            note="Automated deployment"
        )

asyncio.run(main())
```

### Sync Client

```python
from powerbi.powerbi_client import PowerBIClientSync

# For scripts and non-async code
client = PowerBIClientSync()

# List workspaces
workspaces = client.list_workspaces()

# Trigger refresh
client.trigger_refresh("workspace-id", "dataset-id")

# Deploy pipeline
client.deploy_pipeline("pipeline-id", source_stage=0)
```

### Export Refresh History

```python
async with PowerBIClient() as client:
    files = await client.export_refresh_history(
        workspace_id="workspace-guid",
        output_dir="/data/refresh_history"
    )
    
    # Creates:
    # - 20231215_1430_workspace-guid_DatasetsMetadata.json
    # - 20231215_1430_workspace-guid_DatasetRefreshHistory.json
    # - 20231215_1430_workspace-guid_DataflowMetadata.json
    # - 20231215_1430_workspace-guid_DataflowRefreshHistory.json
```

## REST API Endpoints

### Health Check

```bash
# Check Power BI connectivity
curl http://localhost:8000/powerbi/health
```

### Workspaces

```bash
# List workspaces
curl http://localhost:8000/powerbi/workspaces

# List with filter
curl "http://localhost:8000/powerbi/workspaces?filter=isOnDedicatedCapacity%20eq%20true"

# Create workspace
curl -X POST http://localhost:8000/powerbi/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "New Workspace", "capacity_id": "capacity-guid"}'

# Delete workspace
curl -X DELETE http://localhost:8000/powerbi/workspaces/{workspace_id}

# Generate DTAP workspaces
curl -X POST http://localhost:8000/powerbi/workspaces/dtap \
  -H "Content-Type: application/json" \
  -d '{
    "base_name": "Sales Analytics",
    "capacity_id": "capacity-guid",
    "stages": ["dev", "tst", ""]
  }'
```

### Datasets

```bash
# List datasets in workspace
curl http://localhost:8000/powerbi/workspaces/{workspace_id}/datasets

# Get refresh history
curl http://localhost:8000/powerbi/workspaces/{workspace_id}/datasets/{dataset_id}/refresh-history

# Trigger refresh
curl -X POST http://localhost:8000/powerbi/datasets/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "workspace-guid",
    "dataset_id": "dataset-guid"
  }'
```

### Deployment Pipelines

```bash
# List pipelines
curl http://localhost:8000/powerbi/pipelines

# Deploy pipeline
curl -X POST http://localhost:8000/powerbi/pipelines/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_id": "pipeline-guid",
    "source_stage": 0,
    "note": "Production deployment"
  }'
```

### Dataflows

```bash
# List dataflows
curl http://localhost:8000/powerbi/workspaces/{workspace_id}/dataflows
```

### Reports

```bash
# List reports
curl http://localhost:8000/powerbi/workspaces/{workspace_id}/reports
```

### Capacities

```bash
# List capacities
curl http://localhost:8000/powerbi/capacities
```

### Fabric Operations

```bash
# List Fabric workspaces
curl http://localhost:8000/fabric/workspaces

# Generate training workspaces
curl -X POST http://localhost:8000/fabric/workspaces/training \
  -H "Content-Type: application/json" \
  -d '{
    "base_name": "Workshop Feb 2024",
    "count": 20,
    "capacity_id": "capacity-guid"
  }'
```

## Integration with CX Orchestrate

The Power BI module integrates with the CX orchestration pipeline:

```php
<?php
// In cx_orchestrate.php
require_once __DIR__ . '/../powerbi/PowerBIAutomation.php';

use function CXFlow\PowerBI\orch_run_powerbi_integration;

// After data processing, trigger Power BI operations
$pbiResult = orch_run_powerbi_integration([
    'processed_file' => $outputFile,
    'record_count' => $recordCount,
]);

// This will:
// 1. Trigger dataset refresh (if PBI_WORKSPACE_ID and PBI_DATASET_ID are set)
// 2. Deploy pipeline (if PBI_PIPELINE_ID and PBI_DEPLOY_STAGE are set)
```

## Supported Operations

| Category | Operation | PHP Function | Python Method | API Endpoint |
|----------|-----------|--------------|---------------|--------------|
| **Auth** | Authenticate | `pbi_authenticate()` | `authenticate()` | - |
| **Workspaces** | List | `pbi_list_workspaces()` | `list_workspaces()` | `GET /powerbi/workspaces` |
| | List (Admin) | `pbi_list_workspaces_admin()` | `list_workspaces_admin()` | - |
| | Create | `pbi_create_workspace()` | `create_workspace()` | `POST /powerbi/workspaces` |
| | Delete | `pbi_delete_workspace()` | `delete_workspace()` | `DELETE /powerbi/workspaces/{id}` |
| | Assign Capacity | `pbi_assign_workspace_to_capacity()` | `assign_to_capacity()` | - |
| | Add User | `pbi_add_user_to_workspace()` | `add_user_to_workspace()` | - |
| | Add SPN | `pbi_add_spn_to_workspace()` | `add_spn_to_workspace()` | - |
| | DTAP Generate | `pbi_generate_dtap_workspaces()` | `generate_dtap_workspaces()` | `POST /powerbi/workspaces/dtap` |
| **Datasets** | List | `pbi_list_datasets()` | `list_datasets()` | `GET /powerbi/workspaces/{id}/datasets` |
| | Get Parameters | `pbi_get_dataset_parameters()` | `get_dataset_parameters()` | - |
| | Update Parameters | `pbi_update_dataset_parameters()` | `update_dataset_parameters()` | - |
| | Trigger Refresh | `pbi_trigger_refresh()` | `trigger_refresh()` | `POST /powerbi/datasets/refresh` |
| | Refresh History | `pbi_get_refresh_history()` | `get_refresh_history()` | `GET .../refresh-history` |
| | Update Datasource | `pbi_update_datasource()` | `update_datasource()` | - |
| **Pipelines** | List | `pbi_list_pipelines()` | `list_pipelines()` | `GET /powerbi/pipelines` |
| | Add User | `pbi_add_user_to_pipeline()` | `add_user_to_pipeline()` | - |
| | Deploy | `pbi_deploy_pipeline()` | `deploy_pipeline()` | `POST /powerbi/pipelines/deploy` |
| **Dataflows** | List | `pbi_list_dataflows()` | `list_dataflows()` | `GET .../dataflows` |
| | Get Definition | `pbi_get_dataflow_definition()` | `get_dataflow_definition()` | - |
| | Move | `pbi_move_dataflow()` | - | - |
| **Reports** | List | `pbi_list_reports()` | `list_reports()` | `GET .../reports` |
| | Rebind | `pbi_rebind_report()` | `rebind_report()` | - |
| **XMLA** | Get Endpoint | `pbi_get_xmla_endpoint()` | `get_xmla_endpoint()` | - |
| | Backup TMSL | `pbi_tmsl_backup()` | `tmsl_backup()` | - |
| | Refresh Table TMSL | `pbi_tmsl_refresh_table()` | `tmsl_refresh_table()` | - |
| | Assign Role TMSL | `pbi_tmsl_assign_role()` | `tmsl_assign_role()` | - |
| **Fabric** | List Workspaces | `fabric_list_workspaces()` | `fabric_list_workspaces()` | `GET /fabric/workspaces` |
| | Create Workspace | `fabric_create_workspace()` | `fabric_create_workspace()` | - |
| | Training Workspaces | `fabric_generate_training_workspaces()` | `fabric_generate_training_workspaces()` | `POST /fabric/workspaces/training` |

## Permissions Reference

| Operation | Required Permission |
|-----------|-------------------|
| List workspaces | Workspace access |
| List workspaces (admin) | Power BI Service Administrator |
| Create workspace | Workspace creation enabled |
| Assign to capacity | Capacity assignment permissions |
| Trigger refresh | Dataset.ReadWrite.All |
| Deploy pipeline | Pipeline Admin/Contributor |
| Add user to workspace (admin) | Tenant.ReadWrite.All |
| XMLA operations | Power BI Premium |

## Error Handling

All functions return structured responses:

```php
// PHP
$result = pbi_create_workspace('My Workspace');
if ($result['success']) {
    $workspace = $result['workspace'];
} else {
    $error = $result['error'];
    $httpCode = $result['http_code'] ?? null;
}
```

```python
# Python (async)
try:
    workspace = await client.create_workspace("My Workspace")
except Exception as e:
    print(f"Error: {e}")
```

## Best Practices

1. **Use Service Principal** for automated scripts
2. **Cache tokens** - the module handles this automatically
3. **Implement retry logic** for transient failures
4. **Use Premium capacity** for XMLA operations
5. **Monitor refresh history** for failures
6. **Use deployment pipelines** for CI/CD instead of manual publishing
