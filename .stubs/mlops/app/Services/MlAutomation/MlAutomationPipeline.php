<?php

declare(strict_types=1);

namespace App\Services\MlAutomation;

use App\Models\MlDataset;
use App\Models\MlModel;
use App\Models\MlRun;
use App\Services\Assistant\AssistantService;
use App\Services\Automl\AutomlClient;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

/**
 * Fully automated ML pipeline orchestrator.
 *
 * Runs server-side, emits webhook events, and optionally generates a model card
 * using the internal assistant layer (kept invisible to end users).
 */
final class MlAutomationPipeline
{
    public function __construct(
        private readonly DatasetLoader $loader,
        private readonly AutomlClient $automl,
        private readonly MlWebhookNotifier $webhook,
        private readonly ?AssistantService $assistant = null,
    ) {
    }

    /**
     * @param array<string, mixed> $overrides
     * @return array<string, mixed>
     */
    public function run(string $pipeline = 'default', array $overrides = [], ?string $traceId = null): array
    {
        if (!(bool) config('ml_automation.enabled', false)) {
            return ['ok' => false, 'error' => 'disabled'];
        }

        $traceId = $traceId ?? TraceHelper::generate();
        $runEvents = [];

        /** @var array<string, mixed> $pipelines */
        $pipelines = (array) config('ml_automation.pipelines', []);
        /** @var array<string, mixed> $cfg */
        $cfg = (array) ($pipelines[$pipeline] ?? []);
        $cfg = array_replace_recursive($cfg, $overrides);

        $runUuid = (string) Str::uuid();
        $startedAt = now();

        // Create MlRun record
        $mlRun = MlRun::create([
            'run_uuid' => $runUuid,
            'pipeline' => $pipeline,
            'kind' => 'train',
            'status' => 'running',
            'payload' => [
                'trace_id' => $traceId,
                'pipeline' => $pipeline,
                'overrides' => $overrides,
            ],
            'started_at' => $startedAt,
        ]);

        $this->emit($runEvents, 'ml.run.started', [
            'run_uuid' => $runUuid,
            'pipeline' => $pipeline,
            'started_at' => $startedAt->toIso8601String(),
        ], $traceId);

        $source = (string) ($cfg['source'] ?? '');
        $format = (string) ($cfg['format'] ?? 'auto');

        try {
            $rows = $this->loader->loadRows($source, $format);
        } catch (\Throwable $e) {
            $mlRun->update([
                'status' => 'failed',
                'error' => 'Failed to load dataset: ' . $e->getMessage(),
                'finished_at' => now(),
            ]);

            $this->emit($runEvents, 'ml.ingest.failed', [
                'run_uuid' => $runUuid,
                'pipeline' => $pipeline,
                'source' => $source,
                'error' => $e->getMessage(),
            ], $traceId);

            throw $e;
        }

        if (count($rows) < 5) {
            $mlRun->update([
                'status' => 'failed',
                'error' => 'Insufficient rows',
                'finished_at' => now(),
            ]);

            $this->emit($runEvents, 'ml.ingest.failed', [
                'run_uuid' => $runUuid,
                'pipeline' => $pipeline,
                'source' => $source,
                'row_count' => count($rows),
            ], $traceId);

            $this->maybeEmitSingleSummary($runUuid, $pipeline, $startedAt, [
                'ok' => false,
                'error' => 'insufficient_rows',
                'run_uuid' => $runUuid,
                'pipeline' => $pipeline,
                'started_at' => $startedAt->toIso8601String(),
                'finished_at' => now()->toIso8601String(),
                'events' => $runEvents,
            ], $traceId);
            
            return ['ok' => false, 'error' => 'insufficient_rows', 'run_uuid' => $runUuid];
        }

        $webhookCfg = (array) config('ml_automation.webhook', []);
        $includeRows = (bool) config('ml_automation.ingest.include_rows', false);
        $rowPayload = WebhookPayloadHelper::preparePayload($webhookCfg, $rows);

        $target = (string) ($cfg['target'] ?? '');
        if ($target === '') {
            $target = $this->guessTargetColumn($rows);
        }

        $problem = $cfg['problem'] ?? null;
        $metric = $cfg['metric'] ?? null;

        // Persist dataset
        $datasetUuid = (string) Str::uuid();
        $mlDataset = MlDataset::create([
            'dataset_uuid' => $datasetUuid,
            'name' => $pipeline . '_' . $startedAt->format('YmdHis'),
            'source' => $source,
            'schema' => ['columns' => array_keys((array) ($rows[0] ?? []))],
            'row_count' => count($rows),
            'target' => $target,
            'meta' => [
                'trace_id' => $traceId,
                'run_uuid' => $runUuid,
            ],
        ]);

        $this->emit($runEvents, 'ml.ingest.completed', [
            'run_uuid' => $runUuid,
            'dataset_uuid' => $datasetUuid,
            'pipeline' => $pipeline,
            'row_count' => count($rows),
            'columns' => array_keys((array) ($rows[0] ?? [])),
            'target' => $target,
            'source' => $source,
            ...$rowPayload,
        ], $traceId);

        // Train via AutoML microservice
        try {
            $trainResult = $this->automl->train(
                rows: $rows,
                target: $target,
                problem: is_string($problem) ? $problem : null,
                metric: is_string($metric) ? $metric : null,
                traceId: $traceId,
            );
        } catch (\Throwable $e) {
            $mlRun->update([
                'status' => 'failed',
                'error' => 'Training failed: ' . $e->getMessage(),
                'finished_at' => now(),
            ]);

            $this->emit($runEvents, 'ml.train.failed', [
                'run_uuid' => $runUuid,
                'dataset_uuid' => $datasetUuid,
                'pipeline' => $pipeline,
                'request' => [
                    'target' => $target,
                    'problem' => $problem,
                    'metric' => $metric,
                    ...$rowPayload,
                ],
                'error' => 'training_failed',
            ], $traceId);

            $this->maybeEmitSingleSummary($runUuid, $pipeline, $startedAt, [
                'ok' => false,
                'error' => 'training_failed',
                'run_uuid' => $runUuid,
                'pipeline' => $pipeline,
                'started_at' => $startedAt->toIso8601String(),
                'finished_at' => now()->toIso8601String(),
                'events' => $runEvents,
            ], $traceId);
            
            throw $e;
        }

        $modelCard = null;
        $assistantEnabled = (bool) (($cfg['assistant']['enabled'] ?? true) && config('ml_automation.pipelines.' . $pipeline . '.assistant.enabled', true));
        $modelCardEnabled = (bool) (($cfg['assistant']['generate_model_card'] ?? true) && config('ml_automation.pipelines.' . $pipeline . '.assistant.generate_model_card', true));

        if ($assistantEnabled && $modelCardEnabled) {
            $modelCard = $this->tryGenerateModelCard($rows, $target, $trainResult);
        }

        // Persist model as candidate
        $modelUuid = (string) Str::uuid();
        $mlModel = MlModel::create([
            'model_uuid' => $modelUuid,
            'dataset_uuid' => $datasetUuid,
            'automl_model_id' => $trainResult['model_id'],
            'status' => 'candidate',
            'problem' => $trainResult['problem'],
            'metric' => $trainResult['metric'],
            'score' => $trainResult['score'],
            'features' => $trainResult['features'],
            'train_result' => $trainResult,
            'model_card' => $modelCard,
            'meta' => [
                'trace_id' => $traceId,
                'run_uuid' => $runUuid,
                'pipeline' => $pipeline,
            ],
            'trained_at' => now(),
        ]);

        // Auto-promote if enabled
        $autoPromote = (bool) ($cfg['auto_promote'] ?? true);
        if ($autoPromote) {
            $this->promoteModel($mlModel);
        }

        $artifact = [
            'ok' => true,
            'run_uuid' => $runUuid,
            'dataset_uuid' => $datasetUuid,
            'model_uuid' => $modelUuid,
            'pipeline' => $pipeline,
            'started_at' => $startedAt->toIso8601String(),
            'finished_at' => now()->toIso8601String(),
            'dataset' => [
                'source' => $source,
                'row_count' => count($rows),
                'target' => $target,
                'columns' => array_keys((array) ($rows[0] ?? [])),
                ...($includeRows ? ['rows' => $rows] : []),
            ],
            'train' => $trainResult,
            'model_card' => $modelCard,
            'promoted' => $autoPromote,
        ];

        $this->storeArtifact($runUuid, $artifact);

        // Update run as completed
        $mlRun->update([
            'status' => 'completed',
            'result' => $artifact,
            'finished_at' => now(),
        ]);

        $this->emit($runEvents, 'ml.train.completed', [
            'run_uuid' => $runUuid,
            'dataset_uuid' => $datasetUuid,
            'model_uuid' => $modelUuid,
            'pipeline' => $pipeline,
            'request' => [
                'target' => $target,
                'problem' => $problem,
                'metric' => $metric,
                ...$rowPayload,
            ],
            'response' => $trainResult,
            'model_card' => $modelCard,
        ], $traceId);

        $this->emit($runEvents, 'ml.run.completed', [
            'run_uuid' => $runUuid,
            'dataset_uuid' => $datasetUuid,
            'model_uuid' => $modelUuid,
            'pipeline' => $pipeline,
            'model_id' => $trainResult['model_id'],
            'promoted' => $autoPromote,
        ], $traceId);

        $this->maybeEmitSingleSummary($runUuid, $pipeline, $startedAt, $artifact + [
            'events' => $runEvents,
        ], $traceId);

        return $artifact;
    }

    /**
     * Promote model to active and archive previous active.
     */
    private function promoteModel(MlModel $model): void
    {
        // Archive all current active models with same dataset
        MlModel::where('dataset_uuid', $model->dataset_uuid)
            ->where('status', 'active')
            ->update(['status' => 'archived']);

        // Promote this model
        $model->update([
            'status' => 'active',
            'promoted_at' => now(),
        ]);
    }

    /**
     * @param array<int, array{event:string, timestamp:string, data:array<string,mixed>}> $runEvents
     * @param array<string, mixed> $payload
     */
    private function emit(array &$runEvents, string $event, array $payload, ?string $traceId = null): void
    {
        $runEvents[] = [
            'event' => $event,
            'timestamp' => now()->toIso8601String(),
            'data' => $payload,
        ];

        $this->webhook->notify($event, $payload, $traceId);
    }

    /**
     * Emits a single aggregated run payload when enabled.
     *
     * @param array<string, mixed> $artifact
     */
    private function maybeEmitSingleSummary(string $runUuid, string $pipeline, \Illuminate\Support\Carbon $startedAt, array $artifact, ?string $traceId = null): void
    {
        if (!(bool) config('ml_automation.webhook.single_summary', false)) {
            return;
        }

        $this->webhook->notify('ml.run.payload', [
            'run_uuid' => $runUuid,
            'pipeline' => $pipeline,
            'started_at' => $startedAt->toIso8601String(),
            'artifact' => $artifact,
        ], $traceId);
    }

    /**
     * @param array<int, array<string, mixed>> $rows
     */
    private function guessTargetColumn(array $rows): string
    {
        $cols = array_keys((array) ($rows[0] ?? []));
        $preferred = ['target', 'label', 'y', 'class', 'outcome'];
        foreach ($preferred as $p) {
            foreach ($cols as $c) {
                if (Str::lower((string) $c) === $p) {
                    return (string) $c;
                }
            }
        }

        return (string) (end($cols) ?: 'target');
    }

    /**
     * @param array<int, array<string, mixed>> $rows
     * @param array<string, mixed> $trainResult
     * @return array<string, mixed>|null
     */
    private function tryGenerateModelCard(array $rows, string $target, array $trainResult): ?array
    {
        if ($this->assistant === null) {
            return null;
        }

        $sample = array_slice($rows, 0, 15);

        $schema = [
            'type' => 'object',
            'additionalProperties' => false,
            'properties' => [
                'summary' => ['type' => 'string'],
                'target' => ['type' => 'string'],
                'problem' => ['type' => 'string'],
                'metric' => ['type' => 'string'],
                'score_interpretation' => ['type' => 'string'],
                'feature_notes' => ['type' => 'array', 'items' => ['type' => 'string']],
                'data_quality_flags' => ['type' => 'array', 'items' => ['type' => 'string']],
                'limitations' => ['type' => 'array', 'items' => ['type' => 'string']],
                'recommended_next_steps' => ['type' => 'array', 'items' => ['type' => 'string']],
            ],
            'required' => ['summary', 'target', 'problem', 'metric', 'score_interpretation', 'limitations', 'recommended_next_steps'],
        ];

        $prompt = "Generate an internal model card for this trained model.\n" .
            "- Keep it short, practical, and implementation-focused.\n" .
            "- Do NOT mention any provider, vendor, or model name.\n\n" .
            "Training result:\n" . json_encode($trainResult, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n\n" .
            "Target column: {$target}\n" .
            "Sample rows (truncated):\n" . json_encode($sample, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);

        try {
            return $this->assistant->jsonSchema(
                prompt: $prompt,
                schema: $schema,
                schemaName: 'model_card',
                options: [
                    'temperature' => 0.2,
                    'cache_enabled' => false,
                ],
            );
        } catch (\Throwable) {
            return null;
        }
    }

    /**
     * @param array<string, mixed> $artifact
     */
    private function storeArtifact(string $runUuid, array $artifact): void
    {
        $disk = (string) config('ml_automation.storage.disk', 'local');
        $base = trim((string) config('ml_automation.storage.base_path', 'ml'), '/');
        $path = $base . '/runs/' . $runUuid . '.json';

        Storage::disk($disk)->put($path, json_encode($artifact, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
    }
}
