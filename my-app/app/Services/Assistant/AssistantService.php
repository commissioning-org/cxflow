<?php

declare(strict_types=1);

namespace App\Services\Assistant;

use App\Services\Assistant\Contracts\Assistant as AssistantContract;
use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Arr;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;

/**
 * Higher-level automation helpers on top of AssistantClient.
 *
 * Goals:
 * - easy: one call for text/json
 * - robust: retries + backoff
 * - fast: optional caching
 * - quiet: never exposes provider/model details to end users
 */
final class AssistantService implements AssistantContract
{
    public function __construct(private readonly AssistantClient $client)
    {
    }

    /**
     * Basic text completion.
     */
    public function text(string $prompt, array $options = []): string
    {
        $options = $this->normalizeOptions($options);

        $this->enforceRateLimit();
        $this->guardCircuitBreaker();

        $messages = [
            ['role' => 'system', 'content' => $options['system'] ?? $this->defaultSystem()],
            ['role' => 'user', 'content' => $prompt],
        ];

        if ((bool) config('assistant.logging.log_prompts', false)) {
            $this->log('assistant.prompt', ['kind' => 'text', 'messages' => $messages]);
        }

        $result = $this->withCachingAndRetries(
            kind: 'text',
            cacheKey: $this->cacheKey('text', $messages, $options),
            ttlSeconds: $options['cache_ttl_seconds'],
            enabled: $options['cache_enabled'],
            fn: function () use ($messages, $options): string {
                return $this->client->chatText(
                    messages: $messages,
                    model: $options['model'],
                    temperature: $options['temperature'],
                    maxTokens: $options['max_tokens'],
                    tools: $options['tools'],
                    toolChoice: $options['tool_choice'],
                    responseFormat: $options['response_format'],
                );
            },
        );

        if ((bool) config('assistant.logging.log_responses', false)) {
            $this->log('assistant.response', ['kind' => 'text', 'text' => $result]);
        }

        return $result;
    }

    /**
     * Structured JSON response with retries.
     *
     * Returns decoded JSON array; throws if it can't be parsed within retry budget.
     *
     * @return array<string, mixed>
     */
    public function json(string $prompt, array $options = []): array
    {
        $options = $this->normalizeOptions($options);

        $this->enforceRateLimit();
        $this->guardCircuitBreaker();

        $messages = [
            ['role' => 'system', 'content' => $options['system'] ?? $this->defaultSystem()],
            ['role' => 'user', 'content' => $this->forceJsonPrompt($prompt)],
        ];

        if ((bool) config('assistant.logging.log_prompts', false)) {
            $this->log('assistant.prompt', ['kind' => 'json', 'messages' => $messages]);
        }

        $raw = $this->withCachingAndRetries(
            kind: 'json',
            cacheKey: $this->cacheKey('json', $messages, $options),
            ttlSeconds: $options['cache_ttl_seconds'],
            enabled: $options['cache_enabled'],
            fn: function () use ($messages, $options): string {
                return $this->client->chatText(
                    messages: $messages,
                    model: $options['model'],
                    temperature: $options['temperature'],
                    maxTokens: $options['max_tokens'],
                    tools: $options['tools'],
                    toolChoice: $options['tool_choice'],
                    responseFormat: $options['response_format'] ?? ['type' => 'json_object'],
                );
            },
        );

        $decoded = $this->decodeJsonBestEffort($raw);
        if ($decoded !== null) {
            if ((bool) config('assistant.logging.log_responses', false)) {
                $this->log('assistant.response', ['kind' => 'json', 'json' => $decoded]);
            }
            return $decoded;
        }

        // One more tight retry loop specifically for JSON validity.
        $maxJsonFixAttempts = (int) ($options['json_fix_attempts'] ?? 2);
        for ($i = 0; $i < $maxJsonFixAttempts; $i++) {
            $repair = $this->text(
                prompt: "Return ONLY valid JSON for this content, with no extra text. Content:\n" . $raw,
                options: array_merge($options, ['temperature' => 0.0, 'cache_enabled' => false, 'response_format' => ['type' => 'json_object']]),
            );

            $decoded = $this->decodeJsonBestEffort($repair);
            if ($decoded !== null) {
                if ((bool) config('assistant.logging.log_responses', false)) {
                    $this->log('assistant.response', ['kind' => 'json', 'json' => $decoded]);
                }
                return $decoded;
            }
        }

        throw new \RuntimeException('Assistant returned an invalid JSON response.');
    }

    /**
     * JSON Schema helper (OpenAI-compatible when supported by the gateway).
     * Falls back to best-effort JSON if schema mode isn't supported upstream.
     *
     * @param array<string, mixed> $schema
     * @return array<string, mixed>
     */
    public function jsonSchema(string $prompt, array $schema, string $schemaName = 'schema', array $options = []): array
    {
        $options = $this->normalizeOptions($options);
        $options['response_format'] = [
            'type' => 'json_schema',
            'json_schema' => [
                'name' => $schemaName,
                'schema' => $schema,
                'strict' => true,
            ],
        ];

        return $this->json($prompt, $options);
    }

    /**
     * @return array{model:?string, temperature:float, max_tokens:?int, system:?string, cache_enabled:bool, cache_ttl_seconds:int, retries:int, retry_base_delay_ms:int, tools:?array, tool_choice:mixed, json_fix_attempts:int, response_format:?array}
     */
    private function normalizeOptions(array $options): array
    {
        $cfg = (array) config('assistant.inference');
        $defaults = (array) config('assistant.defaults', []);

        return [
            'model' => $options['model'] ?? ($cfg['model'] ?? null),
            'temperature' => (float) ($options['temperature'] ?? ($defaults['temperature'] ?? 0.2)),
            'max_tokens' => $options['max_tokens'] ?? ($defaults['max_tokens'] ?? null),
            'system' => $options['system'] ?? null,

            'response_format' => $options['response_format'] ?? ($defaults['response_format'] ?? null),

            'cache_enabled' => (bool) ($options['cache_enabled'] ?? config('assistant.cache.enabled', true)),
            'cache_ttl_seconds' => (int) ($options['cache_ttl_seconds'] ?? config('assistant.cache.ttl_seconds', 300)),

            'retries' => (int) ($options['retries'] ?? config('assistant.retries.count', 2)),
            'retry_base_delay_ms' => (int) ($options['retry_base_delay_ms'] ?? config('assistant.retries.base_delay_ms', 250)),

            'tools' => $options['tools'] ?? null,
            'tool_choice' => $options['tool_choice'] ?? ($defaults['tool_choice'] ?? null),

            'json_fix_attempts' => (int) ($options['json_fix_attempts'] ?? config('assistant.json.fix_attempts', 2)),
        ];
    }

    private function defaultSystem(): string
    {
        return (string) config('assistant.defaults.system', 'Be concise and accurate.');
    }

    private function forceJsonPrompt(string $prompt): string
    {
        $prefix = (string) config('assistant.json.force_json_prompt', 'You must reply with ONLY a single valid JSON object. Do not include markdown.');
        return rtrim($prefix) . "\n\n" . $prompt;
    }

    /**
     * @param array<int, array{role:string, content:string}> $messages
     */
    private function cacheKey(string $kind, array $messages, array $options): string
    {
        $payload = json_encode([
            'k' => $kind,
            'm' => $messages,
            'o' => Arr::only($options, ['model', 'temperature', 'max_tokens', 'system', 'tool_choice', 'response_format']),
        ]);

        $prefix = (string) config('assistant.cache.key_prefix', 'assistant:');
        $prefix = rtrim($prefix, ':') . ':';
        return $prefix . $kind . ':' . hash('sha256', (string) $payload);
    }

    /**
     * @template T
     * @param callable():T $fn
     * @return T
     */
    private function withCachingAndRetries(string $kind, string $cacheKey, int $ttlSeconds, bool $enabled, callable $fn)
    {
        $cacheSampleRate = (float) config('assistant.cache.sample_rate', 1.0);
        $shouldCache = $enabled && $cacheSampleRate > 0 && (mt_rand() / mt_getrandmax()) <= $cacheSampleRate;

        if ($shouldCache) {
            $cached = Cache::get($cacheKey);
            if ($cached !== null) {
                $this->log('assistant.cache_hit', ['kind' => $kind]);
                return $cached;
            }
            $this->log('assistant.cache_miss', ['kind' => $kind]);
        }

        $runner = function () use ($kind, $fn) {
            $t0 = microtime(true);
            try {
                $out = $fn();
                $this->recordCircuitBreakerSuccess();
                return $out;
            } finally {
                $ms = (int) round((microtime(true) - $t0) * 1000);
                $this->log('assistant.call', ['kind' => $kind, 'ms' => $ms]);
            }
        };

        $value = $this->withRetries($runner);

        if ($shouldCache) {
            Cache::put($cacheKey, $value, $ttlSeconds);
        }

        return $value;
    }

    /**
     * @template T
     * @param callable():T $fn
     * @return T
     */
    private function withRetries(callable $fn)
    {
        $count = (int) config('assistant.retries.count', 2);
        $baseDelayMs = (int) config('assistant.retries.base_delay_ms', 250);
        $maxDelayMs = (int) config('assistant.retries.max_delay_ms', 2000);
        $jitterMs = (int) config('assistant.retries.jitter_ms', 150);

        $attempt = 0;
        while (true) {
            try {
                return $fn();
            } catch (\Throwable $e) {
                $this->recordCircuitBreakerFailure($e);

                if ($attempt >= $count || !$this->isRetryable($e)) {
                    throw $e;
                }

                $sleepMs = $baseDelayMs * (2 ** $attempt);
                $sleepMs = min($sleepMs, $maxDelayMs);
                if ($jitterMs > 0) {
                    $sleepMs += random_int(0, $jitterMs);
                }

                $attempt++;
                $this->log('assistant.retry', ['attempt' => $attempt, 'sleep_ms' => $sleepMs]);
                usleep($sleepMs * 1000);
            }
        }
    }

    private function isRetryable(\Throwable $e): bool
    {
        $retryOnConnection = (bool) config('assistant.retries.retry_on_connection_errors', true);
        $retryOnStatus = (array) config('assistant.retries.retry_on_status', [429, 500, 502, 503, 504]);

        $cur = $e;
        while ($cur !== null) {
            if ($cur instanceof RequestException) {
                $status = $cur->response?->status();
                if (is_int($status)) {
                    return in_array($status, $retryOnStatus, true);
                }
                return $retryOnConnection;
            }
            $cur = $cur->getPrevious();
        }

        return false;
    }

    private function enforceRateLimit(): void
    {
        $cfg = (array) config('assistant.rate_limit', []);
        if (!(bool) ($cfg['enabled'] ?? false)) {
            return;
        }

        $max = (int) ($cfg['max_per_minute'] ?? 60);
        if ($max <= 0) {
            return;
        }

        $keyPrefix = (string) config('assistant.cache.key_prefix', 'assistant:');
        $keyPrefix = rtrim($keyPrefix, ':') . ':';
        $bucket = now()->format('YmdHi');
        $key = $keyPrefix . 'rl:' . $bucket;

        $count = (int) Cache::increment($key);
        if ($count === 1) {
            Cache::put($key, 1, now()->addSeconds(70));
        }

        if ($count > $max) {
            throw new \RuntimeException('Assistant temporarily unavailable.');
        }
    }

    private function guardCircuitBreaker(): void
    {
        $cfg = (array) config('assistant.circuit_breaker', []);
        if (!(bool) ($cfg['enabled'] ?? false)) {
            return;
        }

        $keyPrefix = (string) config('assistant.cache.key_prefix', 'assistant:');
        $keyPrefix = rtrim($keyPrefix, ':') . ':';
        $openUntilKey = $keyPrefix . 'cb:open_until';

        $openUntil = Cache::get($openUntilKey);
        if (!is_string($openUntil) || $openUntil === '') {
            return;
        }

        try {
            if (now()->lt(Carbon::parse($openUntil))) {
                throw new \RuntimeException('Assistant temporarily unavailable.');
            }
        } catch (\Throwable) {
            // If the stored timestamp is malformed, just ignore it.
            Cache::forget($openUntilKey);
        }
    }

    private function recordCircuitBreakerFailure(\Throwable $e): void
    {
        $cfg = (array) config('assistant.circuit_breaker', []);
        if (!(bool) ($cfg['enabled'] ?? false)) {
            return;
        }

        $threshold = (int) ($cfg['failure_threshold'] ?? 10);
        $cooldownSeconds = (int) ($cfg['cooldown_seconds'] ?? 60);
        if ($threshold <= 0 || $cooldownSeconds <= 0) {
            return;
        }

        $keyPrefix = (string) config('assistant.cache.key_prefix', 'assistant:');
        $keyPrefix = rtrim($keyPrefix, ':') . ':';
        $failKey = $keyPrefix . 'cb:failures';
        $openUntilKey = $keyPrefix . 'cb:open_until';

        $fails = (int) Cache::increment($failKey);
        if ($fails === 1) {
            Cache::put($failKey, 1, now()->addSeconds($cooldownSeconds * 2));
        }

        if ($fails >= $threshold) {
            Cache::put(
                $openUntilKey,
                now()->addSeconds($cooldownSeconds)->toIso8601String(),
                now()->addSeconds($cooldownSeconds + 10),
            );
            $this->log('assistant.circuit_opened', ['fails' => $fails]);
        }
    }

    private function recordCircuitBreakerSuccess(): void
    {
        $cfg = (array) config('assistant.circuit_breaker', []);
        if (!(bool) ($cfg['enabled'] ?? false)) {
            return;
        }

        $keyPrefix = (string) config('assistant.cache.key_prefix', 'assistant:');
        $keyPrefix = rtrim($keyPrefix, ':') . ':';
        Cache::forget($keyPrefix . 'cb:failures');
        Cache::forget($keyPrefix . 'cb:open_until');
    }

    /**
     * @param array<string, mixed> $context
     */
    private function log(string $event, array $context = []): void
    {
        $cfg = (array) config('assistant.logging', []);
        if (!(bool) ($cfg['enabled'] ?? true)) {
            return;
        }

        $level = (string) ($cfg['level'] ?? 'debug');
        $safe = $this->redact($context);

        if (!method_exists(Log::class, $level)) {
            $level = 'debug';
        }

        Log::$level($event, $safe);
    }

    /**
     * @param mixed $value
     * @return mixed
     */
    private function redact(mixed $value): mixed
    {
        $cfg = (array) config('assistant.logging', []);
        $redactKeys = array_map(fn ($x) => Str::lower((string) $x), (array) ($cfg['redact_keys'] ?? []));

        if (is_array($value)) {
            $out = [];
            foreach ($value as $k => $v) {
                if (is_string($k) && in_array(Str::lower($k), $redactKeys, true)) {
                    $out[$k] = '[redacted]';
                    continue;
                }
                $out[$k] = $this->redact($v);
            }
            return $out;
        }

        return $value;
    }

    /**
     * @return array<string, mixed>|null
     */
    private function decodeJsonBestEffort(string $raw): ?array
    {
        $raw = trim($raw);

        // If model accidentally wrapped text, try to extract the first JSON object.
        $start = strpos($raw, '{');
        $end = strrpos($raw, '}');
        if ($start !== false && $end !== false && $end > $start) {
            $raw = substr($raw, $start, $end - $start + 1);
        }

        try {
            /** @var mixed */
            $decoded = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
            if (is_array($decoded)) {
                return $decoded;
            }
        } catch (\Throwable) {
            // ignore
        }

        return null;
    }
}
