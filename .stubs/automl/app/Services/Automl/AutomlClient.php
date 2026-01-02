<?php

declare(strict_types=1);

namespace App\Services\Automl;

use Illuminate\Support\Facades\Http;
use App\Services\Automl\AutomlWebhookNotifier;
use App\Services\MlAutomation\WebhookPayloadHelper;

final class AutomlClient
{
    public function __construct(private readonly AutomlWebhookNotifier $webhook)
    {
    }

    /**
     * @param array<int, array<string, mixed>> $rows
     * @return array{model_id:string, problem:string, metric:string, score:float, features:array<int,string>}
     */
    public function train(array $rows, string $target, ?string $problem = null, ?string $metric = null, ?string $traceId = null): array
    {
        $baseUrl = rtrim((string) config('automl.base_url'), '/');
        $timeout = (int) config('automl.timeout_seconds', 60);
        $webhookCfg = (array) config('automl.webhook', []);

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

            // Use helper to prepare webhook payload
            $payload = WebhookPayloadHelper::preparePayload($webhookCfg, $rows, [
                'target' => $target,
                'problem' => $problem,
                'metric' => $metric,
            ]);

            $payload = WebhookPayloadHelper::withTraceId([
                'request' => $payload,
                'response' => $result,
            ], $traceId);

            $this->webhook->notify('automl.train.completed', $payload);

            return $result;
        } catch (\Throwable $e) {
            // Keep errors generic (internal service).
            $payload = WebhookPayloadHelper::preparePayload($webhookCfg, $rows, [
                'target' => $target,
                'problem' => $problem,
                'metric' => $metric,
            ]);

            $payload = WebhookPayloadHelper::withTraceId([
                'request' => $payload,
                'error' => 'training_failed',
            ], $traceId);

            $this->webhook->notify('automl.train.failed', $payload);
            throw new \RuntimeException('AutoML training failed.', (int) $e->getCode(), $e);
        }
    }

    /**
     * @param array<int, array<string, mixed>> $rows
     * @return array<int, mixed>
     */
    public function predict(string $modelId, array $rows, ?string $traceId = null): array
    {
        $baseUrl = rtrim((string) config('automl.base_url'), '/');
        $timeout = (int) config('automl.timeout_seconds', 60);
        $webhookCfg = (array) config('automl.webhook', []);
        $samplePreds = max(0, (int) ($webhookCfg['sample_predictions'] ?? 200));
        $fullPayload = (bool) ($webhookCfg['full_payload'] ?? false);

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
            $predSample = ($samplePreds > 0 && count($out) > 0) ? array_slice($out, 0, $samplePreds) : [];

            $payload = WebhookPayloadHelper::preparePayload($webhookCfg, $rows, [
                'model_id' => $modelId,
            ]);

            $responseData = [
                'prediction_count' => count($out),
                'prediction_sample' => $predSample,
            ];

            if ($fullPayload || $samplePreds === 0) {
                $responseData['predictions'] = $out;
            }

            $payload = WebhookPayloadHelper::withTraceId([
                'request' => $payload,
                'response' => $responseData,
            ], $traceId);

            $this->webhook->notify('automl.predict.completed', $payload);

            return $out;
        } catch (\Throwable $e) {
            $payload = WebhookPayloadHelper::preparePayload($webhookCfg, $rows, [
                'model_id' => $modelId,
            ]);

            $payload = WebhookPayloadHelper::withTraceId([
                'request' => $payload,
                'error' => 'prediction_failed',
            ], $traceId);

            $this->webhook->notify('automl.predict.failed', $payload);
            throw new \RuntimeException('AutoML prediction failed.', (int) $e->getCode(), $e);
        }
    }
}
