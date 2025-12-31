<?php

declare(strict_types=1);

namespace App\Services\MlAutomation;

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
     * @return array<string, mixed>
     */
    public function run(string $pipeline = 'default', array $overrides = []): array
    {
        if (!(bool) config('ml_automation.enabled', false)) {
            return ['ok' => false, 'error' => 'disabled'];
        }

        $runEvents = [];

        /** @var array<string, mixed> $pipelines */
        $pipelines = (array) config('ml_automation.pipelines', []);
        /** @var array<string, mixed> $cfg */
        $cfg = (array) ($pipelines[$pipeline] ?? []);
        $cfg = array_replace_recursive($cfg, $overrides);

        $runId = (string) Str::uuid();
        $startedAt = now()->toIso8601String();

        $this->emit($runEvents, 'ml.run.started', [
            'run_id' => $runId,
            'pipeline' => $pipeline,
            'started_at' => $startedAt,
        ]);

        $source = (string) ($cfg['source'] ?? '');
        $format = (string) ($cfg['format'] ?? 'auto');

        $rows = $this->loader->loadRows($source, $format);
        if (count($rows) < 5) {
            $this->emit($runEvents, 'ml.ingest.failed', [
                'run_id' => $runId,
                'pipeline' => $pipeline,
                'source' => $source,
                'row_count' => count($rows),
            ]);

            $this->maybeEmitSingleSummary($runId, $pipeline, $startedAt, [
                'ok' => false,
                'error' => 'insufficient_rows',
                'run_id' => $runId,
                'pipeline' => $pipeline,
                'started_at' => $startedAt,
                'finished_at' => now()->toIso8601String(),
                'events' => $runEvents,
            ]);
            return ['ok' => false, 'error' => 'insufficient_rows'];
        }

        $includeRows = (bool) config('ml_automation.ingest.include_rows', false);
        $hookIncludeRows = (bool) config('ml_automation.webhook.include_rows', false);
        $sampleRows = max(0, (int) config('ml_automation.webhook.sample_rows', (int) config('ml_automation.ingest.sample_rows', 50)));
        $rowSample = $sampleRows > 0 ? array_slice($rows, 0, $sampleRows) : [];

        $target = (string) ($cfg['target'] ?? '');
        if ($target === '') {
            $target = $this->guessTargetColumn($rows);
        }

        $problem = $cfg['problem'] ?? null;
        $metric = $cfg['metric'] ?? null;

        $this->emit($runEvents, 'ml.ingest.completed', [
            'run_id' => $runId,
            'pipeline' => $pipeline,
            'row_count' => count($rows),
            'columns' => array_keys((array) ($rows[0] ?? [])),
            'target' => $target,
            'source' => $source,
            'row_sample' => $rowSample,
            ...( $hookIncludeRows ? ['rows' => $rows] : [] ),
        ]);

        // Train via AutoML microservice
        try {
            $trainResult = $this->automl->train(
                rows: $rows,
                target: $target,
                problem: is_string($problem) ? $problem : null,
                metric: is_string($metric) ? $metric : null,
            );
        } catch (\Throwable $e) {
            $this->emit($runEvents, 'ml.train.failed', [
                'run_id' => $runId,
                'pipeline' => $pipeline,
                'request' => [
                    'target' => $target,
                    'problem' => $problem,
                    'metric' => $metric,
                    'row_count' => count($rows),
                    'row_sample' => $rowSample,
                    ...( $hookIncludeRows ? ['rows' => $rows] : [] ),
                ],
                'error' => 'training_failed',
            ]);

            $this->maybeEmitSingleSummary($runId, $pipeline, $startedAt, [
                'ok' => false,
                'error' => 'training_failed',
                'run_id' => $runId,
                'pipeline' => $pipeline,
                'started_at' => $startedAt,
                'finished_at' => now()->toIso8601String(),
                'events' => $runEvents,
            ]);
            throw $e;
        }

        $modelCard = null;
        $assistantEnabled = (bool) (($cfg['assistant']['enabled'] ?? true) && config('ml_automation.pipelines.' . $pipeline . '.assistant.enabled', true));
        $modelCardEnabled = (bool) (($cfg['assistant']['generate_model_card'] ?? true) && config('ml_automation.pipelines.' . $pipeline . '.assistant.generate_model_card', true));

        if ($assistantEnabled && $modelCardEnabled) {
            $modelCard = $this->tryGenerateModelCard($rows, $target, $trainResult);
        }

        $artifact = [
            'ok' => true,
            'run_id' => $runId,
            'pipeline' => $pipeline,
            'started_at' => $startedAt,
            'finished_at' => now()->toIso8601String(),
            'dataset' => [
                'source' => $source,
                'row_count' => count($rows),
                'target' => $target,
                'columns' => array_keys((array) ($rows[0] ?? [])),
                'row_sample' => $rowSample,
                ...( $includeRows ? ['rows' => $rows] : [] ),
            ],
            'train' => $trainResult,
            'model_card' => $modelCard,
        ];

        $this->storeArtifact($runId, $artifact);

        $this->emit($runEvents, 'ml.train.completed', [
            'run_id' => $runId,
            'pipeline' => $pipeline,
            'request' => [
                'target' => $target,
                'problem' => $problem,
                'metric' => $metric,
                'row_count' => count($rows),
                'row_sample' => $rowSample,
                ...( $hookIncludeRows ? ['rows' => $rows] : [] ),
            ],
            'response' => $trainResult,
            'model_card' => $modelCard,
        ]);

        $this->emit($runEvents, 'ml.run.completed', [
            'run_id' => $runId,
            'pipeline' => $pipeline,
            'model_id' => (string) ($trainResult['model_id'] ?? ''),
        ]);

        $this->maybeEmitSingleSummary($runId, $pipeline, $startedAt, $artifact + [
            'events' => $runEvents,
        ]);

        return $artifact;
    }

    /**
     * @param array<int, array{event:string, timestamp:string, data:array<string,mixed>}> $runEvents
     * @param array<string, mixed> $payload
     */
    private function emit(array &$runEvents, string $event, array $payload): void
    {
        $runEvents[] = [
            'event' => $event,
            'timestamp' => now()->toIso8601String(),
            'data' => $payload,
        ];

        $this->webhook->notify($event, $payload);
    }

    /**
     * Emits a single aggregated run payload when enabled.
     *
     * @param array<string, mixed> $artifact
     */
    private function maybeEmitSingleSummary(string $runId, string $pipeline, string $startedAt, array $artifact): void
    {
        if (!(bool) config('ml_automation.webhook.single_summary', false)) {
            return;
        }

        $this->webhook->notify('ml.run.payload', [
            'run_id' => $runId,
            'pipeline' => $pipeline,
            'started_at' => $startedAt,
            'artifact' => $artifact,
        ]);
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
    private function storeArtifact(string $runId, array $artifact): void
    {
        $disk = (string) config('ml_automation.storage.disk', 'local');
        $base = trim((string) config('ml_automation.storage.base_path', 'ml'), '/');
        $path = $base . '/runs/' . $runId . '.json';

        Storage::disk($disk)->put($path, json_encode($artifact, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
    }
}
