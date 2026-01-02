<?php

declare(strict_types=1);

use App\Http\Controllers\MlAutomationController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| ML Automation API Routes (Internal Only)
|--------------------------------------------------------------------------
|
| These routes provide internal API access to ML automation features.
| They are gated by config flag (ml_automation.api.enabled).
|
| In production, protect these routes with authentication middleware:
|   Route::middleware(['auth:sanctum'])->group(function() { ... });
|
| Or use IP allowlist, API keys, or other security mechanisms.
|
*/

// Check if API is enabled before registering routes
if ((bool) config('ml_automation.api.enabled', false)) {
    Route::prefix('internal/ml')->group(function () {
        // Run management
        Route::post('/runs', [MlAutomationController::class, 'createRun'])
            ->name('ml.runs.create');

        Route::get('/runs/{run_uuid}', [MlAutomationController::class, 'getRun'])
            ->name('ml.runs.get');

        Route::get('/runs/{run_uuid}/artifact', [MlAutomationController::class, 'getRunArtifact'])
            ->name('ml.runs.artifact');

        // Model management
        Route::get('/models', [MlAutomationController::class, 'listModels'])
            ->name('ml.models.list');

        Route::post('/models/{model_uuid}/promote', [MlAutomationController::class, 'promoteModel'])
            ->name('ml.models.promote');
    });
}
