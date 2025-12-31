<?php

declare(strict_types=1);

namespace App\Services\Automl;

use Illuminate\Support\Facades\Http;
use App\Services\Automl\AutomlWebhookNotifier;

final class AutomlClient
{
    public function __construct(private readonly AutomlWebhookNotifier $webhook)
    {
    }

    /**
     * @param array<int, array<string, mixed>> $rows
     * @return array{model_id:string, problem:string, metric:string, score:float, features:array<int,string>}
     */
    public function train(array $rows, string $target, ?string $problem = null, ?string $metric = null): array
    {
        $baseUrl = rtrim((string) config('automl.base_url'), '/');
        $timeout = (int) config('automl.timeout_seconds', 60);
        $includeRows = (bool) config('automl.webhook.include_rows', false);
        $sampleRows = max(0, (int) config('automl.webhook.sample_rows', 50));
        $rowSample = $sampleRows > 0 ? array_slice($rows, 0, $sampleRows) : [];

        try {
            $resp = Http::timeout($timeout)
                ->acceptJson()
                ->asJson()
                ->post($baseUrl . '/train', [
                    'rows' => $rows,
                    'target' => $target,
                    'problem' => $problem,
                    'metric' => $metric,
                ])
                ->throw();

            /** @var array<string, mixed> */
            $json = $resp->json() ?? [];

            $result = [
                'model_id' => (string) ($json['model_id'] ?? ''),
                'problem' => (string) ($json['problem'] ?? ''),
                'metric' => (string) ($json['metric'] ?? ''),
                'score' => (float) ($json['score'] ?? 0.0),
                'features' => is_array($json['features'] ?? null) ? $json['features'] : [],
            ];

            // Post "all automl data" to webhook when enabled.
            $this->webhook->notify('automl.train.completed', [
                'request' => [
                    'target' => $target,
                    'problem' => $problem,
                    'metric' => $metric,
                    'row_count' => count($rows),
                    'row_sample' => $rowSample,
                    ...( $includeRows ? ['rows' => $rows] : [] ),
                ],
                'response' => $result,
            ]);

            return $result;
        } catch (\Throwable $e) {
            // Keep errors generic (internal service).
            $this->webhook->notify('automl.train.failed', [
                'request' => [
                    'target' => $target,
                    'problem' => $problem,
                    'metric' => $metric,
                    'row_count' => count($rows),
                    'row_sample' => $rowSample,
                    ...( $includeRows ? ['rows' => $rows] : [] ),
                ],
                'error' => 'training_failed',
            ]);
            throw new \RuntimeException('AutoML training failed.', (int) $e->getCode(), $e);
        }
    }

    /**
     * @param array<int, array<string, mixed>> $rows
     * @return array<int, mixed>
     */
    public function predict(string $modelId, array $rows): array
    {
        $baseUrl = rtrim((string) config('automl.base_url'), '/');
        $timeout = (int) config('automl.timeout_seconds', 60);
        $includeRows = (bool) config('automl.webhook.include_rows', false);
        $sampleRows = max(0, (int) config('automl.webhook.sample_rows', 50));
        $samplePreds = max(0, (int) config('automl.webhook.sample_predictions', 200));
        $rowSample = $sampleRows > 0 ? array_slice($rows, 0, $sampleRows) : [];

        try {
            $resp = Http::timeout($timeout)
                ->acceptJson()
                ->asJson()
                ->post($baseUrl . '/predict', [
                    'model_id' => $modelId,
                    'rows' => $rows,
                ])
                ->throw();

            /** @var array<string, mixed> */
            $json = $resp->json() ?? [];
            $preds = $json['predictions'] ?? [];

            $out = is_array($preds) ? array_values($preds) : [];
            $predSample = $samplePreds > 0 ? array_slice($out, 0, $samplePreds) : [];

            $this->webhook->notify('automl.predict.completed', [
                'request' => [
                    'model_id' => $modelId,
                    'row_count' => count($rows),
                    'row_sample' => $rowSample,
                    ...( $includeRows ? ['rows' => $rows] : [] ),
                ],
                'response' => [
                    'prediction_count' => count($out),
                    'prediction_sample' => $predSample,
                    ...( $samplePreds === 0 ? ['predictions' => $out] : [] ),
                ],
            ]);

            return $out;
        } catch (\Throwable $e) {
            $this->webhook->notify('automl.predict.failed', [
                'request' => [
                    'model_id' => $modelId,
                    'row_count' => count($rows),
                    'row_sample' => $rowSample,
                    ...( $includeRows ? ['rows' => $rows] : [] ),
                ],
                'error' => 'prediction_failed',
            ]);
            throw new \RuntimeException('AutoML prediction failed.', (int) $e->getCode(), $e);
        }
    }
}
