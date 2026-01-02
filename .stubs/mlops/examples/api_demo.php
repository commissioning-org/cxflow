#!/usr/bin/env php
<?php

/**
 * Example script demonstrating ML Automation API usage.
 * 
 * This script shows how to:
 * 1. Trigger an ML automation run
 * 2. Poll for completion
 * 3. Retrieve results
 * 4. List models
 * 5. Promote a model
 * 
 * Usage:
 *   php .stubs/mlops/examples/api_demo.php
 * 
 * Requirements:
 *   - ML_AUTOMATION_ENABLED=true
 *   - ML_AUTOMATION_API_ENABLED=true
 *   - ML_AUTOMATION_SOURCE configured
 *   - Application running (php artisan serve or similar)
 */

$baseUrl = getenv('APP_URL') ?: 'http://localhost:8000';
$apiBase = rtrim($baseUrl, '/') . '/internal/ml';

echo "ML Automation API Demo\n";
echo "======================\n\n";

// Check if API is reachable
echo "Checking API availability...\n";
$health = @file_get_contents($apiBase . '/models');
if ($health === false) {
    echo "❌ API not reachable at {$apiBase}\n";
    echo "   Make sure:\n";
    echo "   - Application is running (php artisan serve)\n";
    echo "   - ML_AUTOMATION_API_ENABLED=true\n";
    exit(1);
}
echo "✓ API is reachable\n\n";

// 1. Trigger a run
echo "1. Triggering ML automation run...\n";
$runPayload = json_encode([
    'pipeline' => 'default',
    'async' => true,
    'overrides' => [
        // Add overrides if needed
    ],
]);

$context = stream_context_create([
    'http' => [
        'method' => 'POST',
        'header' => "Content-Type: application/json\r\n",
        'content' => $runPayload,
    ],
]);

$runResponse = @file_get_contents($apiBase . '/runs', false, $context);
if ($runResponse === false) {
    echo "❌ Failed to trigger run\n";
    exit(1);
}

$runData = json_decode($runResponse, true);
echo "✓ Run triggered\n";
echo "  Trace ID: " . ($runData['trace_id'] ?? 'N/A') . "\n";
echo "  Result Key: " . ($runData['result_key'] ?? 'N/A') . "\n\n";

// Wait a bit for processing
echo "2. Waiting for run to start (5 seconds)...\n";
sleep(5);

// 3. Check for runs in database
echo "\n3. Checking for completed runs...\n";
$modelsResponse = @file_get_contents($apiBase . '/models?limit=5');
if ($modelsResponse === false) {
    echo "❌ Failed to list models\n";
    exit(1);
}

$modelsData = json_decode($modelsResponse, true);
$models = $modelsData['models'] ?? [];

if (empty($models)) {
    echo "ℹ️  No models found yet. Run might still be processing.\n";
    echo "   To see results, wait for the run to complete and run this script again.\n\n";
} else {
    echo "✓ Found " . count($models) . " model(s)\n\n";
    
    foreach ($models as $idx => $model) {
        echo "   Model " . ($idx + 1) . ":\n";
        echo "   - UUID: " . ($model['model_uuid'] ?? 'N/A') . "\n";
        echo "   - Status: " . ($model['status'] ?? 'N/A') . "\n";
        echo "   - Problem: " . ($model['problem'] ?? 'N/A') . "\n";
        echo "   - Metric: " . ($model['metric'] ?? 'N/A') . "\n";
        echo "   - Score: " . ($model['score'] ?? 'N/A') . "\n";
        echo "   - Trained: " . ($model['trained_at'] ?? 'N/A') . "\n";
        
        if ($model['status'] === 'candidate') {
            echo "\n   You can promote this model with:\n";
            echo "   curl -X POST {$apiBase}/models/{$model['model_uuid']}/promote\n";
        }
        echo "\n";
    }
}

// 4. Example: List active models only
echo "4. Listing active models...\n";
$activeResponse = @file_get_contents($apiBase . '/models?status=active');
if ($activeResponse !== false) {
    $activeData = json_decode($activeResponse, true);
    $activeModels = $activeData['models'] ?? [];
    echo "✓ Found " . count($activeModels) . " active model(s)\n\n";
}

echo "Demo complete!\n\n";
echo "Next steps:\n";
echo "- Check CLI: php artisan ml:automate --sync\n";
echo "- View runs: curl {$apiBase}/runs/{{run_uuid}}\n";
echo "- View models: curl {$apiBase}/models\n";
echo "- Promote model: curl -X POST {$apiBase}/models/{{model_uuid}}/promote\n";
