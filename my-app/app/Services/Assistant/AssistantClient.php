<?php

declare(strict_types=1);

namespace App\Services\Assistant;

use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;

/**
 * Internal assistant client.
 *
 * Intentionally avoids exposing provider/model details in return values.
 */
final class AssistantClient
{
    /**
     * @param array<int, array{role:string, content:string}> $messages
     * @return array<string, mixed>
     */
    public function chat(
        array $messages,
        ?string $model = null,
        float $temperature = 0.2,
        ?int $maxTokens = null,
        ?array $tools = null,
        mixed $toolChoice = null,
        ?array $responseFormat = null,
    ): array
    {
        $cfg = config('assistant.inference');

        $baseUrl = rtrim((string) ($cfg['base_url'] ?? ''), '/');
        $token = (string) ($cfg['token'] ?? '');
        $configuredModel = (string) ($cfg['model'] ?? 'grok-3');
        $allowOtherModels = (bool) ($cfg['allow_other_models'] ?? false);
        $timeoutSeconds = (int) ($cfg['timeout_seconds'] ?? 60);
        $connectTimeoutSeconds = (int) ($cfg['connect_timeout_seconds'] ?? 10);
        $path = (string) ($cfg['chat_completions_path'] ?? '/v1/chat/completions');
        /** @var array<string, string> $extraHeaders */
        $extraHeaders = is_array($cfg['headers'] ?? null) ? $cfg['headers'] : [];

        if ($token === '') {
            throw new \RuntimeException('Missing ASSISTANT_API_KEY (or GITHUB_MODELS_TOKEN).');
        }

        $modelToUse = $model ?? $configuredModel;

        // Enforce a single configured model by default.
        if (!$allowOtherModels && Str::lower(trim($modelToUse)) !== Str::lower(trim($configuredModel))) {
            throw new \RuntimeException('Configured model restriction violated.');
        }

        $path = '/' . ltrim($path, '/');
        $url = $baseUrl . $path;

        $requestId = (string) Str::uuid();

        $payload = [
            'model' => $modelToUse,
            'messages' => $messages,
            'temperature' => $temperature,
        ];

        if ($maxTokens !== null) {
            $payload['max_tokens'] = $maxTokens;
        }

        // OpenAI-compatible tool/function calling (optional)
        if (is_array($tools) && count($tools) > 0) {
            $payload['tools'] = $tools;
        }
        if ($toolChoice !== null) {
            $payload['tool_choice'] = $toolChoice;
        }

        // OpenAI-compatible response_format (optional)
        if (is_array($responseFormat) && isset($responseFormat['type'])) {
            $payload['response_format'] = $responseFormat;
        }

        try {
            $resp = Http::timeout($timeoutSeconds)
                ->connectTimeout($connectTimeoutSeconds)
                ->withToken($token)
                ->withHeaders(array_merge([
                    'X-Request-Id' => $requestId,
                ], $extraHeaders))
                ->acceptJson()
                ->asJson()
                ->post($url, $payload)
                ->throw();

            /** @var array<string, mixed> */
            return $resp->json() ?? [];
        } catch (RequestException $e) {
            // Do not leak provider/model details in error text.
            $status = $e->response?->status();
            $code = is_int($status) ? $status : (int) $e->getCode();

            // Preserve retry-relevant context via the previous exception.
            throw new \RuntimeException('Assistant request failed.', $code, $e);
        }
    }

    /**
     * @param array<int, array{role:string, content:string}> $messages
     */
    public function chatText(
        array $messages,
        ?string $model = null,
        float $temperature = 0.2,
        ?int $maxTokens = null,
        ?array $tools = null,
        mixed $toolChoice = null,
        ?array $responseFormat = null,
    ): string
    {
        $data = $this->chat($messages, $model, $temperature, $maxTokens, $tools, $toolChoice, $responseFormat);

        $choices = $data['choices'] ?? null;
        if (is_array($choices) && isset($choices[0]['message']['content']) && is_string($choices[0]['message']['content'])) {
            return $choices[0]['message']['content'];
        }

        return '';
    }
}
