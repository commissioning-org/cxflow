<?php
/**
 * Power BI Automation Module
 * 
 * Comprehensive PHP implementation based on marclelijveld/Power-BI-Automation
 * Provides workspace management, deployment pipelines, dataset operations,
 * XMLA endpoints, and dataflow management for Power BI and Microsoft Fabric.
 * 
 * @author CXFlow Integration
 * @version 1.0.0
 * @see https://github.com/marclelijveld/Power-BI-Automation
 */

declare(strict_types=1);

namespace CXFlow\PowerBI;

// ============================================================================
// Configuration
// ============================================================================

/**
 * Get Power BI configuration from environment variables.
 */
function pbi_get_config(): array {
    return [
        'tenant_id' => getenv('PBI_TENANT_ID') ?: '',
        'client_id' => getenv('PBI_CLIENT_ID') ?: '',
        'client_secret' => getenv('PBI_CLIENT_SECRET') ?: '',
        'username' => getenv('PBI_USERNAME') ?: '',
        'password' => getenv('PBI_PASSWORD') ?: '',
        'auth_mode' => getenv('PBI_AUTH_MODE') ?: 'service_principal', // 'service_principal' or 'user'
        'api_base' => 'https://api.powerbi.com/v1.0/myorg/',
        'fabric_api_base' => 'https://api.fabric.microsoft.com/v1/',
        'xmla_base' => 'powerbi://api.powerbi.com/v1.0/myorg/',
        'timeout' => (int)(getenv('PBI_TIMEOUT') ?: 30),
        'retry_count' => (int)(getenv('PBI_RETRY_COUNT') ?: 3),
    ];
}

// ============================================================================
// Authentication
// ============================================================================

/**
 * Token cache for authenticated sessions.
 */
class TokenCache {
    private static ?string $accessToken = null;
    private static ?int $expiresAt = null;
    
    public static function get(): ?string {
        if (self::$accessToken && self::$expiresAt && time() < self::$expiresAt - 60) {
            return self::$accessToken;
        }
        return null;
    }
    
    public static function set(string $token, int $expiresIn): void {
        self::$accessToken = $token;
        self::$expiresAt = time() + $expiresIn;
    }
    
    public static function clear(): void {
        self::$accessToken = null;
        self::$expiresAt = null;
    }
}

/**
 * Authenticate with Azure AD and get access token.
 * 
 * Supports both Service Principal and User authentication.
 * 
 * @param array|null $config Configuration override
 * @return array{success: bool, token?: string, error?: string, expires_in?: int}
 */
function pbi_authenticate(?array $config = null): array {
    $config = $config ?? pbi_get_config();
    
    // Check cache first
    $cached = TokenCache::get();
    if ($cached) {
        return ['success' => true, 'token' => $cached, 'cached' => true];
    }
    
    $tokenUrl = "https://login.microsoftonline.com/{$config['tenant_id']}/oauth2/v2.0/token";
    
    if ($config['auth_mode'] === 'service_principal') {
        // Service Principal authentication
        $postData = http_build_query([
            'grant_type' => 'client_credentials',
            'client_id' => $config['client_id'],
            'client_secret' => $config['client_secret'],
            'scope' => 'https://analysis.windows.net/powerbi/api/.default',
        ]);
    } else {
        // User authentication (Resource Owner Password Credentials)
        $postData = http_build_query([
            'grant_type' => 'password',
            'client_id' => $config['client_id'],
            'username' => $config['username'],
            'password' => $config['password'],
            'scope' => 'https://analysis.windows.net/powerbi/api/.default',
        ]);
    }
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => $tokenUrl,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $postData,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => $config['timeout'],
        CURLOPT_HTTPHEADER => ['Content-Type: application/x-www-form-urlencoded'],
    ]);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);
    
    if ($error) {
        return ['success' => false, 'error' => "cURL error: $error"];
    }
    
    $data = json_decode($response, true);
    
    if ($httpCode !== 200 || !isset($data['access_token'])) {
        $errMsg = $data['error_description'] ?? $data['error'] ?? 'Authentication failed';
        return ['success' => false, 'error' => $errMsg, 'http_code' => $httpCode];
    }
    
    TokenCache::set($data['access_token'], $data['expires_in'] ?? 3600);
    
    return [
        'success' => true,
        'token' => $data['access_token'],
        'expires_in' => $data['expires_in'] ?? 3600,
        'token_type' => $data['token_type'] ?? 'Bearer',
    ];
}

/**
 * Make an authenticated API request to Power BI.
 * 
 * @param string $method HTTP method (GET, POST, PATCH, DELETE)
 * @param string $endpoint API endpoint (relative to base URL)
 * @param array|null $body Request body for POST/PATCH
 * @param array|null $config Configuration override
 * @param bool $useFabricApi Use Fabric API instead of Power BI API
 * @return array{success: bool, data?: mixed, error?: string, http_code?: int}
 */
function pbi_request(
    string $method,
    string $endpoint,
    ?array $body = null,
    ?array $config = null,
    bool $useFabricApi = false
): array {
    $config = $config ?? pbi_get_config();
    
    // Authenticate
    $auth = pbi_authenticate($config);
    if (!$auth['success']) {
        return $auth;
    }
    
    $baseUrl = $useFabricApi ? $config['fabric_api_base'] : $config['api_base'];
    $url = $baseUrl . ltrim($endpoint, '/');
    
    $headers = [
        "Authorization: Bearer {$auth['token']}",
        'Content-Type: application/json',
    ];
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => $config['timeout'],
        CURLOPT_HTTPHEADER => $headers,
    ]);
    
    switch (strtoupper($method)) {
        case 'POST':
            curl_setopt($ch, CURLOPT_POST, true);
            if ($body !== null) {
                curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
            }
            break;
        case 'PATCH':
            curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'PATCH');
            if ($body !== null) {
                curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
            }
            break;
        case 'DELETE':
            curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'DELETE');
            break;
        case 'PUT':
            curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'PUT');
            if ($body !== null) {
                curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
            }
            break;
    }
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);
    
    if ($error) {
        return ['success' => false, 'error' => "cURL error: $error"];
    }
    
    // Handle empty responses (204 No Content)
    if ($httpCode === 204 || empty($response)) {
        return ['success' => true, 'data' => null, 'http_code' => $httpCode];
    }
    
    $data = json_decode($response, true);
    
    if ($httpCode >= 400) {
        $errMsg = $data['error']['message'] ?? $data['message'] ?? 'Request failed';
        return ['success' => false, 'error' => $errMsg, 'http_code' => $httpCode, 'response' => $data];
    }
    
    return ['success' => true, 'data' => $data, 'http_code' => $httpCode];
}

// ============================================================================
// Workspace Management
// ============================================================================

/**
 * List all workspaces the authenticated user has access to.
 * 
 * @param int $top Maximum number of results
 * @param int $skip Number of results to skip
 * @param string|null $filter OData filter expression
 * @return array{success: bool, workspaces?: array, error?: string}
 */
function pbi_list_workspaces(int $top = 100, int $skip = 0, ?string $filter = null): array {
    $endpoint = "groups?\$top=$top&\$skip=$skip";
    if ($filter) {
        $endpoint .= "&\$filter=" . urlencode($filter);
    }
    
    $result = pbi_request('GET', $endpoint);
    
    if ($result['success']) {
        return ['success' => true, 'workspaces' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * List workspaces as admin (requires Power BI Service Administrator).
 * 
 * @param int $top Maximum results
 * @param string|null $filter OData filter (e.g., "isOnDedicatedCapacity eq true")
 * @param string $expand Fields to expand (users, datasets, reports, dashboards, dataflows)
 * @return array
 */
function pbi_list_workspaces_admin(int $top = 100, ?string $filter = null, string $expand = ''): array {
    $endpoint = "admin/groups?\$top=$top";
    if ($filter) {
        $endpoint .= "&\$filter=" . urlencode($filter);
    }
    if ($expand) {
        $endpoint .= "&\$expand=$expand";
    }
    
    $result = pbi_request('GET', $endpoint);
    
    if ($result['success']) {
        return ['success' => true, 'workspaces' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Get Premium capacity workspaces.
 */
function pbi_get_premium_workspaces(int $top = 100): array {
    return pbi_list_workspaces_admin($top, 'isOnDedicatedCapacity eq true');
}

/**
 * Create a new workspace.
 * 
 * @param string $name Workspace name
 * @return array{success: bool, workspace?: array, error?: string}
 */
function pbi_create_workspace(string $name): array {
    $result = pbi_request('POST', 'groups', ['name' => $name]);
    
    if ($result['success']) {
        return ['success' => true, 'workspace' => $result['data']];
    }
    
    return $result;
}

/**
 * Delete a workspace.
 * 
 * @param string $workspaceId Workspace GUID
 * @return array{success: bool, error?: string}
 */
function pbi_delete_workspace(string $workspaceId): array {
    return pbi_request('DELETE', "groups/$workspaceId");
}

/**
 * Assign workspace to a Premium capacity.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $capacityId Capacity GUID
 * @return array{success: bool, error?: string}
 */
function pbi_assign_workspace_to_capacity(string $workspaceId, string $capacityId): array {
    return pbi_request('POST', "groups/$workspaceId/AssignToCapacity", [
        'capacityId' => $capacityId,
    ]);
}

/**
 * Unassign workspace from Premium capacity.
 * 
 * @param string $workspaceId Workspace GUID
 * @return array{success: bool, error?: string}
 */
function pbi_unassign_workspace_from_capacity(string $workspaceId): array {
    return pbi_request('POST', "groups/$workspaceId/AssignToCapacity", [
        'capacityId' => '00000000-0000-0000-0000-000000000000',
    ]);
}

/**
 * Set workspace storage format to Large Dataset.
 * 
 * @param string $workspaceId Workspace GUID
 * @return array
 */
function pbi_set_large_dataset_format(string $workspaceId): array {
    return pbi_request('PATCH', "groups/$workspaceId", [
        'defaultDatasetStorageFormat' => 'Large',
    ]);
}

/**
 * Add user to workspace.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $email User email/UPN
 * @param string $role Permission level (Admin, Member, Contributor, Viewer)
 * @param bool $asAdmin Use admin API
 * @return array
 */
function pbi_add_user_to_workspace(
    string $workspaceId,
    string $email,
    string $role = 'Contributor',
    bool $asAdmin = false
): array {
    $endpoint = $asAdmin 
        ? "admin/groups/$workspaceId/users"
        : "groups/$workspaceId/users";
    
    return pbi_request('POST', $endpoint, [
        'emailAddress' => $email,
        'groupUserAccessRight' => $role,
    ]);
}

/**
 * Add Service Principal to workspace.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $objectId Enterprise Application Object ID (not App ID!)
 * @param string $role Permission level
 * @return array
 */
function pbi_add_spn_to_workspace(
    string $workspaceId,
    string $objectId,
    string $role = 'Contributor'
): array {
    return pbi_request('POST', "admin/groups/$workspaceId/users", [
        'identifier' => $objectId,
        'groupUserAccessRight' => $role,
        'principalType' => 'App',
    ]);
}

/**
 * Remove user from workspace.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $email User email/UPN
 * @return array
 */
function pbi_remove_user_from_workspace(string $workspaceId, string $email): array {
    return pbi_request('DELETE', "admin/groups/$workspaceId/users/" . urlencode($email));
}

/**
 * Generate DTAP workspaces (Dev/Test/Prod).
 * 
 * @param string $baseName Base workspace name
 * @param string $capacityId Premium capacity GUID
 * @param array $stages Stage suffixes (default: dev, tst, prd)
 * @return array{success: bool, workspaces?: array, errors?: array}
 */
function pbi_generate_dtap_workspaces(
    string $baseName,
    string $capacityId,
    array $stages = ['dev', 'tst', '']
): array {
    $created = [];
    $errors = [];
    
    foreach ($stages as $stage) {
        $wsName = $stage ? "{$baseName}-{$stage}" : $baseName;
        
        // Create workspace
        $result = pbi_create_workspace($wsName);
        if (!$result['success']) {
            $errors[] = ['stage' => $stage, 'error' => $result['error']];
            continue;
        }
        
        $wsId = $result['workspace']['id'];
        
        // Assign to capacity
        $assignResult = pbi_assign_workspace_to_capacity($wsId, $capacityId);
        if (!$assignResult['success']) {
            $errors[] = ['stage' => $stage, 'error' => "Capacity assignment failed: " . $assignResult['error']];
        }
        
        // Set large dataset format
        pbi_set_large_dataset_format($wsId);
        
        $created[] = [
            'name' => $wsName,
            'id' => $wsId,
            'stage' => $stage ?: 'prod',
        ];
    }
    
    return [
        'success' => count($errors) === 0,
        'workspaces' => $created,
        'errors' => $errors,
    ];
}

// ============================================================================
// Deployment Pipeline Management
// ============================================================================

/**
 * List all deployment pipelines.
 * 
 * @return array{success: bool, pipelines?: array}
 */
function pbi_list_pipelines(): array {
    $result = pbi_request('GET', 'pipelines');
    
    if ($result['success']) {
        return ['success' => true, 'pipelines' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * List all pipelines as admin (with stages).
 * 
 * @return array
 */
function pbi_list_pipelines_admin(): array {
    $result = pbi_request('GET', 'admin/pipelines?$expand=stages');
    
    if ($result['success']) {
        return ['success' => true, 'pipelines' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Get pipeline users.
 * 
 * @param string $pipelineId Pipeline GUID
 * @return array
 */
function pbi_get_pipeline_users(string $pipelineId): array {
    return pbi_request('GET', "admin/pipelines/$pipelineId/users");
}

/**
 * Add user to deployment pipeline.
 * 
 * @param string $pipelineId Pipeline GUID
 * @param string $identifier User UPN or Object ID
 * @param string $accessRight Permission level (Admin, Contributor, Viewer)
 * @param string $principalType Principal type (User, Group, App)
 * @return array
 */
function pbi_add_user_to_pipeline(
    string $pipelineId,
    string $identifier,
    string $accessRight = 'Admin',
    string $principalType = 'User'
): array {
    return pbi_request('POST', "admin/pipelines/$pipelineId/users", [
        'identifier' => $identifier,
        'accessRight' => $accessRight,
        'principalType' => $principalType,
    ]);
}

/**
 * Trigger deployment pipeline (deploy all artifacts).
 * 
 * @param string $pipelineId Pipeline GUID
 * @param int $sourceStageOrder Source stage (0 = Dev, 1 = Test)
 * @param string $note Deployment note
 * @param array $options Deployment options
 * @return array
 */
function pbi_deploy_pipeline(
    string $pipelineId,
    int $sourceStageOrder = 0,
    string $note = '',
    array $options = []
): array {
    $body = [
        'sourceStageOrder' => $sourceStageOrder,
        'options' => array_merge([
            'allowOverwriteArtifact' => true,
            'allowCreateArtifact' => true,
        ], $options),
    ];
    
    if ($note) {
        $body['note'] = $note;
    }
    
    return pbi_request('POST', "pipelines/$pipelineId/deployAll", $body);
}

/**
 * Deploy specific datasets from pipeline.
 * 
 * @param string $pipelineId Pipeline GUID
 * @param int $sourceStageOrder Source stage
 * @param array $datasets Array of dataset configurations
 * @return array
 */
function pbi_deploy_pipeline_datasets(
    string $pipelineId,
    int $sourceStageOrder,
    array $datasets
): array {
    return pbi_request('POST', "pipelines/$pipelineId/deploy", [
        'sourceStageOrder' => $sourceStageOrder,
        'datasets' => $datasets,
        'options' => [
            'allowOverwriteArtifact' => true,
        ],
    ]);
}

// ============================================================================
// Dataset Operations
// ============================================================================

/**
 * List datasets in a workspace.
 * 
 * @param string $workspaceId Workspace GUID
 * @return array{success: bool, datasets?: array}
 */
function pbi_list_datasets(string $workspaceId): array {
    $result = pbi_request('GET', "groups/$workspaceId/datasets");
    
    if ($result['success']) {
        return ['success' => true, 'datasets' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Get dataset parameters.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $datasetId Dataset GUID
 * @return array
 */
function pbi_get_dataset_parameters(string $workspaceId, string $datasetId): array {
    $result = pbi_request('GET', "groups/$workspaceId/datasets/$datasetId/parameters");
    
    if ($result['success']) {
        return ['success' => true, 'parameters' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Update dataset parameters.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $datasetId Dataset GUID
 * @param array $parameters Array of [name => value] pairs
 * @return array
 */
function pbi_update_dataset_parameters(
    string $workspaceId,
    string $datasetId,
    array $parameters
): array {
    $updateDetails = array_map(fn($name, $value) => [
        'name' => $name,
        'newValue' => $value,
    ], array_keys($parameters), array_values($parameters));
    
    return pbi_request('POST', "groups/$workspaceId/datasets/$datasetId/Default.UpdateParameters", [
        'updateDetails' => $updateDetails,
    ]);
}

/**
 * Get dataset refresh schedule.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $datasetId Dataset GUID
 * @return array
 */
function pbi_get_refresh_schedule(string $workspaceId, string $datasetId): array {
    return pbi_request('GET', "groups/$workspaceId/datasets/$datasetId/refreshSchedule");
}

/**
 * Get dataset refresh history.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $datasetId Dataset GUID
 * @param int $top Maximum results
 * @return array
 */
function pbi_get_refresh_history(string $workspaceId, string $datasetId, int $top = 100): array {
    $result = pbi_request('GET', "groups/$workspaceId/datasets/$datasetId/refreshes?\$top=$top");
    
    if ($result['success']) {
        return ['success' => true, 'refreshes' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Trigger dataset refresh.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $datasetId Dataset GUID
 * @param string $notifyOption Notification option (MailOnCompletion, MailOnFailure, NoNotification)
 * @return array
 */
function pbi_trigger_refresh(
    string $workspaceId,
    string $datasetId,
    string $notifyOption = 'NoNotification'
): array {
    return pbi_request('POST', "groups/$workspaceId/datasets/$datasetId/refreshes", [
        'notifyOption' => $notifyOption,
    ]);
}

/**
 * Get datasources for a dataset.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $datasetId Dataset GUID
 * @return array
 */
function pbi_get_datasources(string $workspaceId, string $datasetId): array {
    $result = pbi_request('GET', "groups/$workspaceId/datasets/$datasetId/datasources");
    
    if ($result['success']) {
        return ['success' => true, 'datasources' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Update datasource connection (swap connections).
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $datasetId Dataset GUID
 * @param string $datasourceType e.g., 'AnalysisServices'
 * @param array $sourceConnection ['server' => '', 'database' => '']
 * @param array $targetConnection ['server' => '', 'database' => '']
 * @return array
 */
function pbi_update_datasource(
    string $workspaceId,
    string $datasetId,
    string $datasourceType,
    array $sourceConnection,
    array $targetConnection
): array {
    return pbi_request('POST', "groups/$workspaceId/datasets/$datasetId/Default.UpdateDatasources", [
        'updateDetails' => [[
            'datasourceSelector' => [
                'datasourceType' => $datasourceType,
                'connectionDetails' => $sourceConnection,
            ],
            'connectionDetails' => $targetConnection,
        ]],
    ]);
}

/**
 * Rebind report to different dataset.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $reportId Report GUID
 * @param string $targetDatasetId Target dataset GUID
 * @return array
 */
function pbi_rebind_report(string $workspaceId, string $reportId, string $targetDatasetId): array {
    return pbi_request('POST', "groups/$workspaceId/reports/$reportId/Rebind", [
        'datasetId' => $targetDatasetId,
    ]);
}

// ============================================================================
// Dataflow Operations
// ============================================================================

/**
 * List dataflows in a workspace.
 * 
 * @param string $workspaceId Workspace GUID
 * @return array{success: bool, dataflows?: array}
 */
function pbi_list_dataflows(string $workspaceId): array {
    $result = pbi_request('GET', "groups/$workspaceId/dataflows");
    
    if ($result['success']) {
        return ['success' => true, 'dataflows' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Get dataflow definition (model.json).
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $dataflowId Dataflow GUID
 * @return array
 */
function pbi_get_dataflow_definition(string $workspaceId, string $dataflowId): array {
    return pbi_request('GET', "groups/$workspaceId/dataflows/$dataflowId");
}

/**
 * Get dataflow refresh history (transactions).
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $dataflowId Dataflow GUID
 * @return array
 */
function pbi_get_dataflow_transactions(string $workspaceId, string $dataflowId): array {
    $result = pbi_request('GET', "groups/$workspaceId/dataflows/$dataflowId/transactions");
    
    if ($result['success']) {
        return ['success' => true, 'transactions' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Move (copy) dataflow to another workspace.
 * 
 * @param string $sourceWorkspaceId Source workspace GUID
 * @param string $destWorkspaceId Destination workspace GUID
 * @param string $dataflowId Dataflow GUID
 * @param array $replacements Connection string replacements [search => replace]
 * @param string $conflictMode 'Ignore' or 'Overwrite'
 * @return array
 */
function pbi_move_dataflow(
    string $sourceWorkspaceId,
    string $destWorkspaceId,
    string $dataflowId,
    array $replacements = [],
    string $conflictMode = 'Ignore'
): array {
    // Get dataflow definition
    $defResult = pbi_get_dataflow_definition($sourceWorkspaceId, $dataflowId);
    if (!$defResult['success']) {
        return $defResult;
    }
    
    // Convert to JSON and apply replacements
    $definition = json_encode($defResult['data']);
    foreach ($replacements as $search => $replace) {
        $definition = str_replace($search, $replace, $definition);
    }
    
    // Check if dataflow exists in destination
    $existing = pbi_list_dataflows($destWorkspaceId);
    $dataflowName = $defResult['data']['name'] ?? '';
    
    if ($existing['success']) {
        foreach ($existing['dataflows'] as $df) {
            if ($df['name'] === $dataflowName) {
                $conflictMode = 'Overwrite';
                break;
            }
        }
    }
    
    // Import to destination (multipart form upload)
    return pbi_import_dataflow($destWorkspaceId, $definition, $conflictMode);
}

/**
 * Import dataflow definition to workspace.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $definition JSON definition (model.json content)
 * @param string $conflictMode Conflict handling
 * @return array
 */
function pbi_import_dataflow(string $workspaceId, string $definition, string $conflictMode = 'Ignore'): array {
    $config = pbi_get_config();
    $auth = pbi_authenticate($config);
    
    if (!$auth['success']) {
        return $auth;
    }
    
    $url = $config['api_base'] . "groups/$workspaceId/imports?datasetDisplayName=model.json&nameConflict=$conflictMode";
    
    $boundary = uniqid('boundary');
    $body = "--$boundary\r\n";
    $body .= "Content-Disposition: form-data; name=\"\"; filename=\"model.json\"\r\n";
    $body .= "Content-Type: application/json\r\n\r\n";
    $body .= $definition . "\r\n";
    $body .= "--$boundary--\r\n";
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => $url,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $body,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => $config['timeout'],
        CURLOPT_HTTPHEADER => [
            "Authorization: Bearer {$auth['token']}",
            "Content-Type: multipart/form-data; boundary=--$boundary",
        ],
    ]);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    $data = json_decode($response, true);
    
    if ($httpCode >= 400) {
        return ['success' => false, 'error' => $data['error']['message'] ?? 'Import failed', 'http_code' => $httpCode];
    }
    
    return ['success' => true, 'data' => $data];
}

// ============================================================================
// Report Operations
// ============================================================================

/**
 * List reports in a workspace.
 * 
 * @param string $workspaceId Workspace GUID
 * @return array
 */
function pbi_list_reports(string $workspaceId): array {
    $result = pbi_request('GET', "groups/$workspaceId/reports");
    
    if ($result['success']) {
        return ['success' => true, 'reports' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Get report details.
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $reportId Report GUID
 * @return array
 */
function pbi_get_report(string $workspaceId, string $reportId): array {
    return pbi_request('GET', "groups/$workspaceId/reports/$reportId");
}

// ============================================================================
// Capacity Management
// ============================================================================

/**
 * List capacities.
 * 
 * @return array
 */
function pbi_list_capacities(): array {
    $result = pbi_request('GET', 'capacities');
    
    if ($result['success']) {
        return ['success' => true, 'capacities' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

// ============================================================================
// XMLA Endpoint Operations
// ============================================================================

/**
 * Build XMLA endpoint URL.
 * 
 * @param string $workspaceName Workspace name (URL-encoded)
 * @return string
 */
function pbi_get_xmla_endpoint(string $workspaceName): string {
    $config = pbi_get_config();
    $encodedName = str_replace(' ', '%20', $workspaceName);
    return $config['xmla_base'] . $encodedName;
}

/**
 * Generate TMSL backup command.
 * 
 * @param string $datasetName Dataset/database name
 * @param string $backupFile Backup filename (.abf)
 * @param bool $applyCompression Apply compression
 * @return string TMSL JSON command
 */
function pbi_tmsl_backup(string $datasetName, string $backupFile, bool $applyCompression = true): string {
    return json_encode([
        'backup' => [
            'database' => $datasetName,
            'file' => $backupFile,
            'allowOverwrite' => false,
            'applyCompression' => $applyCompression,
        ],
    ], JSON_PRETTY_PRINT);
}

/**
 * Generate TMSL refresh command for specific table.
 * 
 * @param string $datasetName Dataset/database name
 * @param string $tableName Table to refresh
 * @param string $refreshType Refresh type (automatic, full, calculate, dataOnly, clearValues)
 * @return string TMSL JSON command
 */
function pbi_tmsl_refresh_table(string $datasetName, string $tableName, string $refreshType = 'automatic'): string {
    return json_encode([
        'refresh' => [
            'type' => $refreshType,
            'objects' => [[
                'database' => $datasetName,
                'table' => $tableName,
            ]],
        ],
    ], JSON_PRETTY_PRINT);
}

/**
 * Generate TMSL createOrReplace command for role membership.
 * 
 * @param string $datasetName Dataset/database name
 * @param string $roleName Role name
 * @param string $roleDescription Role description
 * @param array $members Array of member identifiers
 * @return string TMSL JSON command
 */
function pbi_tmsl_assign_role(
    string $datasetName,
    string $roleName,
    string $roleDescription,
    array $members
): string {
    $memberObjects = array_map(fn($m) => ['memberName' => $m], $members);
    
    return json_encode([
        'createOrReplace' => [
            'object' => [
                'database' => $datasetName,
                'role' => $roleName,
            ],
            'role' => [
                'name' => $roleName,
                'description' => $roleDescription,
                'modelPermission' => 'read',
                'members' => $memberObjects,
            ],
        ],
    ], JSON_PRETTY_PRINT);
}

// ============================================================================
// Fabric Operations
// ============================================================================

/**
 * List Fabric workspaces.
 * 
 * @return array
 */
function fabric_list_workspaces(): array {
    $result = pbi_request('GET', 'workspaces', null, null, true);
    
    if ($result['success']) {
        return ['success' => true, 'workspaces' => $result['data']['value'] ?? []];
    }
    
    return $result;
}

/**
 * Create Fabric workspace.
 * 
 * @param string $displayName Workspace display name
 * @param string|null $capacityId Capacity GUID
 * @return array
 */
function fabric_create_workspace(string $displayName, ?string $capacityId = null): array {
    $body = ['displayName' => $displayName];
    
    if ($capacityId) {
        $body['capacityId'] = $capacityId;
    }
    
    return pbi_request('POST', 'workspaces', $body, null, true);
}

/**
 * Delete Fabric workspace.
 * 
 * @param string $workspaceId Workspace GUID
 * @return array
 */
function fabric_delete_workspace(string $workspaceId): array {
    return pbi_request('DELETE', "workspaces/$workspaceId", null, null, true);
}

/**
 * Generate training user workspaces (for workshops).
 * 
 * @param string $baseName Base workspace name
 * @param int $count Number of workspaces to create
 * @param string|null $capacityId Capacity GUID
 * @return array{success: bool, workspaces?: array, errors?: array}
 */
function fabric_generate_training_workspaces(string $baseName, int $count, ?string $capacityId = null): array {
    $created = [];
    $errors = [];
    
    for ($i = 1; $i <= $count; $i++) {
        $wsName = "$baseName - User $i";
        
        $result = fabric_create_workspace($wsName, $capacityId);
        
        if ($result['success']) {
            $created[] = [
                'name' => $wsName,
                'id' => $result['data']['id'] ?? null,
                'user_index' => $i,
            ];
        } else {
            $errors[] = [
                'name' => $wsName,
                'user_index' => $i,
                'error' => $result['error'],
            ];
        }
    }
    
    return [
        'success' => count($errors) === 0,
        'workspaces' => $created,
        'errors' => $errors,
    ];
}

/**
 * Delete training workspaces by name pattern.
 * 
 * @param string $namePattern Workspace name pattern (supports * wildcard)
 * @return array{success: bool, deleted?: array, errors?: array}
 */
function fabric_delete_training_workspaces(string $namePattern): array {
    $list = fabric_list_workspaces();
    
    if (!$list['success']) {
        return $list;
    }
    
    // Convert wildcard pattern to regex
    $regex = '/^' . str_replace(['*', '?'], ['.*', '.'], preg_quote($namePattern, '/')) . '$/i';
    
    $deleted = [];
    $errors = [];
    
    foreach ($list['workspaces'] as $ws) {
        if (preg_match($regex, $ws['displayName'])) {
            $result = fabric_delete_workspace($ws['id']);
            
            if ($result['success']) {
                $deleted[] = ['name' => $ws['displayName'], 'id' => $ws['id']];
            } else {
                $errors[] = ['name' => $ws['displayName'], 'id' => $ws['id'], 'error' => $result['error']];
            }
        }
    }
    
    return [
        'success' => count($errors) === 0,
        'deleted' => $deleted,
        'errors' => $errors,
    ];
}

// ============================================================================
// Bulk Operations
// ============================================================================

/**
 * Get all refresh history for a workspace (datasets + dataflows).
 * 
 * @param string $workspaceId Workspace GUID
 * @param string $outputDir Output directory for JSON files
 * @return array
 */
function pbi_export_refresh_history(string $workspaceId, string $outputDir): array {
    if (!is_dir($outputDir)) {
        mkdir($outputDir, 0755, true);
    }
    
    $datePrefix = date('Ymd_Hi');
    $results = [];
    
    // Dataset metadata
    $datasets = pbi_list_datasets($workspaceId);
    if ($datasets['success']) {
        $file = "$outputDir/{$datePrefix}_{$workspaceId}_DatasetsMetadata.json";
        file_put_contents($file, json_encode($datasets['datasets'], JSON_PRETTY_PRINT));
        $results['datasets_metadata'] = $file;
        
        // Dataset refresh history
        $datasetRefreshes = [];
        foreach ($datasets['datasets'] as $ds) {
            $history = pbi_get_refresh_history($workspaceId, $ds['id']);
            if ($history['success']) {
                foreach ($history['refreshes'] as $r) {
                    $r['datasetId'] = $ds['id'];
                    $r['datasetName'] = $ds['name'];
                    $datasetRefreshes[] = $r;
                }
            }
        }
        
        $file = "$outputDir/{$datePrefix}_{$workspaceId}_DatasetRefreshHistory.json";
        file_put_contents($file, json_encode($datasetRefreshes, JSON_PRETTY_PRINT));
        $results['dataset_refresh_history'] = $file;
    }
    
    // Dataflow metadata
    $dataflows = pbi_list_dataflows($workspaceId);
    if ($dataflows['success']) {
        $file = "$outputDir/{$datePrefix}_{$workspaceId}_DataflowMetadata.json";
        file_put_contents($file, json_encode($dataflows['dataflows'], JSON_PRETTY_PRINT));
        $results['dataflows_metadata'] = $file;
        
        // Dataflow transactions
        $dataflowTransactions = [];
        foreach ($dataflows['dataflows'] as $df) {
            $trans = pbi_get_dataflow_transactions($workspaceId, $df['objectId']);
            if ($trans['success']) {
                foreach ($trans['transactions'] as $t) {
                    $t['dataflowId'] = $df['objectId'];
                    $t['dataflowName'] = $df['name'];
                    $dataflowTransactions[] = $t;
                }
            }
        }
        
        $file = "$outputDir/{$datePrefix}_{$workspaceId}_DataflowRefreshHistory.json";
        file_put_contents($file, json_encode($dataflowTransactions, JSON_PRETTY_PRINT));
        $results['dataflow_refresh_history'] = $file;
    }
    
    return ['success' => true, 'files' => $results];
}

// ============================================================================
// Integration with cx_orchestrate
// ============================================================================

/**
 * Power BI orchestration integration.
 * Called from cx_orchestrate.php after data processing.
 * 
 * @param array $context Orchestration context
 * @return array{success: bool, results?: array, error?: string}
 */
function orch_run_powerbi_integration(array $context): array {
    $config = pbi_get_config();
    
    if (empty($config['tenant_id']) || empty($config['client_id'])) {
        return ['success' => false, 'error' => 'Power BI not configured (missing credentials)'];
    }
    
    $results = [];
    
    // Trigger dataset refresh if configured
    $workspaceId = getenv('PBI_WORKSPACE_ID');
    $datasetId = getenv('PBI_DATASET_ID');
    
    if ($workspaceId && $datasetId) {
        $refreshResult = pbi_trigger_refresh($workspaceId, $datasetId);
        $results['dataset_refresh'] = $refreshResult;
    }
    
    // Trigger deployment if configured
    $pipelineId = getenv('PBI_PIPELINE_ID');
    $deployStage = getenv('PBI_DEPLOY_STAGE');
    
    if ($pipelineId && $deployStage !== false) {
        $deployNote = "Automated deployment from CXFlow - " . date('Y-m-d H:i:s');
        $deployResult = pbi_deploy_pipeline($pipelineId, (int)$deployStage, $deployNote);
        $results['pipeline_deploy'] = $deployResult;
    }
    
    return ['success' => true, 'results' => $results];
}
