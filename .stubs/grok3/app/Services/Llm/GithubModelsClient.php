<?php

declare(strict_types=1);

namespace App\Services\Llm;

use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;

final class GithubModelsClient
{
    /**
     * Send a Chat Completions request (OpenAI-compatible) to GitHub Models.
     *
     * @param array<int, array{role:string, content:string}> $messages
     * @param array<string, mixed>|null $responseFormat
     * @return array<string, mixed>
     */
    public function chat(array $messages, ?string $model = null, float $temperature = 0.2, ?int $maxTokens = null, ?array $responseFormat = null): array
    {
        $cfg = config('llm.github_models');

        $baseUrl = rtrim((string) ($cfg['base_url'] ?? ''), '/');
        $token = (string) ($cfg['token'] ?? '');
        $configuredModel = (string) ($cfg['model'] ?? 'grok-3');
        $allowOtherModels = (bool) ($cfg['allow_other_models'] ?? false);
        $timeoutSeconds = (int) ($cfg['timeout_seconds'] ?? 60);
        $retries = (int) ($cfg['retries'] ?? 2);
        $retryBaseDelayMs = (int) ($cfg['retry_base_delay_ms'] ?? 250);
        $retryMaxDelayMs = (int) ($cfg['retry_max_delay_ms'] ?? 2000);
        $retryJitterMs = (int) ($cfg['retry_jitter_ms'] ?? 150);

        if ($token === '') {
            throw new \RuntimeException('Missing GITHUB_MODELS_TOKEN. Set it in your environment (do not commit it).');
        }

        $modelToUse = $model ?? $configuredModel;

        // Enforce "grok-3 only" by default.
        // Guard against accidental whitespace/casing mismatch.
        if (!$allowOtherModels && Str::lower(trim($modelToUse)) !== 'grok-3') {
            throw new \RuntimeException('Model is restricted to grok-3 only.');
        }

        $url = $baseUrl . '/v1/chat/completions';

        $payload = [
            'model' => $modelToUse,
            'messages' => $messages,
            'temperature' => $temperature,
        ];

        if ($maxTokens !== null) {
            $payload['max_tokens'] = $maxTokens;
        }

        if ($responseFormat !== null) {
            $payload['response_format'] = $responseFormat;
        }

        return $this->withRetries(function () use ($url, $token, $timeoutSeconds, $payload) {
            try {
                $resp = Http::timeout($timeoutSeconds)
                    ->withToken($token)
                    ->acceptJson()
                    ->asJson()
                    ->post($url, $payload);

                $statusCode = $resp->status();

                // Throw on error status
                if ($statusCode >= 400) {
                    $body = $resp->json();
                    $errorMsg = is_array($body) ? json_encode($body) : $resp->body();
                    
                    throw new RequestException(
                        $resp,
                        "GitHub Models request failed with status {$statusCode}: {$errorMsg}"
                    );
                }

                /** @var array<string, mixed> */
                return $resp->json() ?? [];
            } catch (RequestException $e) {
                $statusCode = $e->response?->status() ?? 0;
                $body = $e->response?->json();
                $errorMsg = is_array($body) ? json_encode($body) : $e->response?->body();

                throw new \RuntimeException(
                    "GitHub Models request failed (status: {$statusCode}): {$errorMsg}",
                    $statusCode,
                    $e
                );
            }
        }, $retries, $retryBaseDelayMs, $retryMaxDelayMs, $retryJitterMs);
    }

    /**
     * Convenience helper that returns the first assistant message content (if present).
     *
     * @param array<int, array{role:string, content:string}> $messages
     * @param array<string, mixed>|null $responseFormat
     */
    public function chatText(array $messages, ?string $model = null, float $temperature = 0.2, ?int $maxTokens = null, ?array $responseFormat = null): string
    {
        $data = $this->chat($messages, $model, $temperature, $maxTokens, $responseFormat);

        // OpenAI-style: choices[0].message.content
        $choices = $data['choices'] ?? null;
        if (is_array($choices) && isset($choices[0]['message']['content']) && is_string($choices[0]['message']['content'])) {
            return $choices[0]['message']['content'];
        }

        return '';
    }

    /**
     * Helper for structured JSON outputs using JSON Schema (OpenAI-compatible).
     *
     * @param array<int, array{role:string, content:string}> $messages
     * @param array<string, mixed> $schema JSON Schema definition
     * @return array<string, mixed>
     */
    public function jsonSchema(array $messages, array $schema, string $schemaName = 'schema', ?string $model = null, float $temperature = 0.2, ?int $maxTokens = null): array
    {
        $responseFormat = [
            'type' => 'json_schema',
            'json_schema' => [
                'name' => $schemaName,
                'schema' => $schema,
                'strict' => true,
            ],
        ];

        $data = $this->chat($messages, $model, $temperature, $maxTokens, $responseFormat);

        // Parse JSON from response
        $choices = $data['choices'] ?? null;
        if (is_array($choices) && isset($choices[0]['message']['content']) && is_string($choices[0]['message']['content'])) {
            $content = $choices[0]['message']['content'];
            try {
                /** @var array<string, mixed> */
                return json_decode($content, true, 512, JSON_THROW_ON_ERROR);
            } catch (\JsonException) {
                throw new \RuntimeException('Failed to parse JSON response from GitHub Models.');
            }
        }

        throw new \RuntimeException('No valid response from GitHub Models.');
    }

    /**
     * Retry wrapper with exponential backoff and jitter.
     *
     * @template T
     * @param callable():T $fn
     * @return T
     */
    private function withRetries(callable $fn, int $maxRetries, int $baseDelayMs, int $maxDelayMs, int $jitterMs): mixed
    {
        $attempt = 0;
        
        while (true) {
            try {
                return $fn();
            } catch (\Throwable $e) {
                $shouldRetry = $this->isRetryableError($e);
                
                if (!$shouldRetry || $attempt >= $maxRetries) {
                    throw $e;
                }

                $sleepMs = $baseDelayMs * (2 ** $attempt);
                $sleepMs = min($sleepMs, $maxDelayMs);
                
                if ($jitterMs > 0) {
                    $sleepMs += random_int(0, $jitterMs);
                }

                $attempt++;
                usleep($sleepMs * 1000);
            }
        }
    }

    /**
     * Determine if an error is retryable (429, 5xx).
     */
    private function isRetryableError(\Throwable $e): bool
    {
        // Check for HTTP status codes that warrant retry
        if ($e instanceof \RuntimeException) {
            $code = $e->getCode();
            // 429 (rate limit), 500, 502, 503, 504 (server errors)
            return in_array($code, [429, 500, 502, 503, 504], true);
        }

        // Check nested RequestException
        $current = $e;
        while ($current !== null) {
            if ($current instanceof RequestException) {
                $status = $current->response?->status();
                if (is_int($status)) {
                    return in_array($status, [429, 500, 502, 503, 504], true);
                }
            }
            $current = $current->getPrevious();
        }

        return false;
    }
}
