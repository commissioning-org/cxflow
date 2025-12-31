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
     * @return array<string, mixed>
     */
    public function chat(array $messages, ?string $model = null, float $temperature = 0.2, ?int $maxTokens = null): array
    {
        $cfg = config('llm.github_models');

        $baseUrl = rtrim((string) ($cfg['base_url'] ?? ''), '/');
        $token = (string) ($cfg['token'] ?? '');
        $configuredModel = (string) ($cfg['model'] ?? 'grok-3');
        $allowOtherModels = (bool) ($cfg['allow_other_models'] ?? false);
        $timeoutSeconds = (int) ($cfg['timeout_seconds'] ?? 60);

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

        try {
            $resp = Http::timeout($timeoutSeconds)
                ->withToken($token)
                ->acceptJson()
                ->asJson()
                ->post($url, $payload)
                ->throw();

            /** @var array<string, mixed> */
            return $resp->json() ?? [];
        } catch (RequestException $e) {
            $body = $e->response?->json();
            $msg = $e->getMessage();

            if (is_array($body)) {
                $msg .= ' | response=' . json_encode($body);
            }

            throw new \RuntimeException('GitHub Models request failed: ' . $msg, (int) $e->getCode(), $e);
        }
    }

    /**
     * Convenience helper that returns the first assistant message content (if present).
     *
     * @param array<int, array{role:string, content:string}> $messages
     */
    public function chatText(array $messages, ?string $model = null, float $temperature = 0.2, ?int $maxTokens = null): string
    {
        $data = $this->chat($messages, $model, $temperature, $maxTokens);

        // OpenAI-style: choices[0].message.content
        $choices = $data['choices'] ?? null;
        if (is_array($choices) && isset($choices[0]['message']['content']) && is_string($choices[0]['message']['content'])) {
            return $choices[0]['message']['content'];
        }

        return '';
    }
}
