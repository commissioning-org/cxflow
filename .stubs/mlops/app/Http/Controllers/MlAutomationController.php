<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Jobs\RunMlAutomation;
use App\Models\MlModel;
use App\Models\MlRun;
use App\Services\MlAutomation\MlAutomationPipeline;
use App\Services\MlAutomation\TraceHelper;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

/**
 * Internal-only controller for ML automation operations.
 *
 * Gated by config flag (ml_automation.api.enabled).
 * Should be protected by authentication middleware in production.
 */
final class MlAutomationController extends Controller
{
    /**
     * Trigger a new ML automation run.
     *
     * POST /internal/ml/runs
     *
     * Body:
     * {
     *   "pipeline": "default",
     *   "async": true,
     *   "overrides": {
     *     "source": "...",
     *     "target": "...",
     *     "problem": "...",
     *     "metric": "..."
     *   }
     * }
     */
    public function createRun(Request $request, MlAutomationPipeline $pipeline): JsonResponse
    {
        if (!(bool) config('ml_automation.api.enabled', false)) {
            return response()->json(['error' => 'API disabled'], 403);
        }

        $validated = $request->validate([
            'pipeline' => 'string',
            'async' => 'boolean',
            'overrides' => 'array',
        ]);

        $pipelineName = (string) ($validated['pipeline'] ?? 'default');
        $async = (bool) ($validated['async'] ?? true);
        $overrides = (array) ($validated['overrides'] ?? []);

        $traceId = TraceHelper::generate();

        if (!$async) {
            // Synchronous execution
            $artifact = $pipeline->run($pipelineName, $overrides, $traceId);
            return response()->json([
                'ok' => true,
                'trace_id' => $traceId,
                'run_uuid' => $artifact['run_uuid'] ?? null,
                'artifact' => $artifact,
            ]);
        }

        // Asynchronous execution via queue
        $resultKey = 'ml:result:' . Str::uuid();
        Cache::put($resultKey, [
            'ok' => false,
            'pending' => true,
            'trace_id' => $traceId,
        ], now()->addMinutes(10));

        RunMlAutomation::dispatch($pipelineName, $resultKey, $overrides, $traceId);

        return response()->json([
            'ok' => true,
            'trace_id' => $traceId,
            'result_key' => $resultKey,
            'message' => 'Run dispatched. Poll status using result_key or run_uuid (check after a few seconds).',
        ]);
    }

    /**
     * Get status and results of a run.
     *
     * GET /internal/ml/runs/{run_uuid}
     */
    public function getRun(string $runUuid): JsonResponse
    {
        if (!(bool) config('ml_automation.api.enabled', false)) {
            return response()->json(['error' => 'API disabled'], 403);
        }

        $run = MlRun::where('run_uuid', $runUuid)->first();

        if ($run === null) {
            return response()->json(['error' => 'Run not found'], 404);
        }

        return response()->json([
            'ok' => true,
            'run' => [
                'run_uuid' => $run->run_uuid,
                'pipeline' => $run->pipeline,
                'kind' => $run->kind,
                'status' => $run->status,
                'payload' => $run->payload,
                'result' => $run->result,
                'error' => $run->error,
                'started_at' => $run->started_at?->toIso8601String(),
                'finished_at' => $run->finished_at?->toIso8601String(),
                'created_at' => $run->created_at?->toIso8601String(),
                'updated_at' => $run->updated_at?->toIso8601String(),
            ],
        ]);
    }

    /**
     * Get stored artifact for a run.
     *
     * GET /internal/ml/runs/{run_uuid}/artifact
     */
    public function getRunArtifact(string $runUuid): JsonResponse
    {
        if (!(bool) config('ml_automation.api.enabled', false)) {
            return response()->json(['error' => 'API disabled'], 403);
        }

        $run = MlRun::where('run_uuid', $runUuid)->first();

        if ($run === null) {
            return response()->json(['error' => 'Run not found'], 404);
        }

        // Try to load from storage
        $disk = (string) config('ml_automation.storage.disk', 'local');
        $base = trim((string) config('ml_automation.storage.base_path', 'ml'), '/');
        $path = $base . '/runs/' . $runUuid . '.json';

        if (!Storage::disk($disk)->exists($path)) {
            // Fall back to result field if no artifact file
            if ($run->result !== null) {
                return response()->json([
                    'ok' => true,
                    'artifact' => $run->result,
                ]);
            }

            return response()->json(['error' => 'Artifact not found'], 404);
        }

        $content = Storage::disk($disk)->get($path);
        $artifact = json_decode((string) $content, true);

        if (!is_array($artifact)) {
            return response()->json(['error' => 'Invalid artifact'], 500);
        }

        return response()->json([
            'ok' => true,
            'artifact' => $artifact,
        ]);
    }

    /**
     * List models with optional filters.
     *
     * GET /internal/ml/models?status=active&limit=10
     */
    public function listModels(Request $request): JsonResponse
    {
        if (!(bool) config('ml_automation.api.enabled', false)) {
            return response()->json(['error' => 'API disabled'], 403);
        }

        $validated = $request->validate([
            'status' => 'string|in:candidate,active,archived',
            'dataset_uuid' => 'string',
            'limit' => 'integer|min:1|max:100',
        ]);

        $query = MlModel::query();

        if (isset($validated['status'])) {
            $query->where('status', $validated['status']);
        }

        if (isset($validated['dataset_uuid'])) {
            $query->where('dataset_uuid', $validated['dataset_uuid']);
        }

        $limit = (int) ($validated['limit'] ?? 20);
        $models = $query->orderBy('created_at', 'desc')->limit($limit)->get();

        return response()->json([
            'ok' => true,
            'models' => $models->map(fn($m) => [
                'model_uuid' => $m->model_uuid,
                'dataset_uuid' => $m->dataset_uuid,
                'automl_model_id' => $m->automl_model_id,
                'status' => $m->status,
                'problem' => $m->problem,
                'metric' => $m->metric,
                'score' => $m->score,
                'features' => $m->features,
                'train_result' => $m->train_result,
                'model_card' => $m->model_card,
                'meta' => $m->meta,
                'trained_at' => $m->trained_at?->toIso8601String(),
                'promoted_at' => $m->promoted_at?->toIso8601String(),
                'created_at' => $m->created_at?->toIso8601String(),
                'updated_at' => $m->updated_at?->toIso8601String(),
            ])->toArray(),
        ]);
    }

    /**
     * Manually promote a model to active.
     *
     * POST /internal/ml/models/{model_uuid}/promote
     */
    public function promoteModel(string $modelUuid): JsonResponse
    {
        if (!(bool) config('ml_automation.api.enabled', false)) {
            return response()->json(['error' => 'API disabled'], 403);
        }

        $model = MlModel::where('model_uuid', $modelUuid)->first();

        if ($model === null) {
            return response()->json(['error' => 'Model not found'], 404);
        }

        if ($model->status === 'active') {
            return response()->json([
                'ok' => true,
                'message' => 'Model is already active',
                'model_uuid' => $model->model_uuid,
            ]);
        }

        // Archive all current active models with same dataset
        MlModel::where('dataset_uuid', $model->dataset_uuid)
            ->where('status', 'active')
            ->update(['status' => 'archived']);

        // Promote this model
        $model->update([
            'status' => 'active',
            'promoted_at' => now(),
        ]);

        return response()->json([
            'ok' => true,
            'message' => 'Model promoted to active',
            'model_uuid' => $model->model_uuid,
            'promoted_at' => $model->promoted_at?->toIso8601String(),
        ]);
    }
}
