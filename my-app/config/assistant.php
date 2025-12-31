<?php

declare(strict_types=1);

return [
    /*
    |--------------------------------------------------------------------------
    | Assistant (internal automation)
    |--------------------------------------------------------------------------
    |
    | This app can call an external inference API through an OpenAI-compatible
    | endpoint. Keep provider/model details out of user-facing outputs.
    |
    */

    // Future-proof: allows swapping providers without touching call sites.
    'provider' => env('ASSISTANT_PROVIDER', 'inference'),

    'inference' => [
        // OpenAI-compatible base URL
        'base_url' => env('ASSISTANT_BASE_URL', env('GITHUB_MODELS_BASE_URL', 'https://models.inference.ai.azure.com')),

        // Secret token (do not commit)
        'token' => env('ASSISTANT_API_KEY', env('GITHUB_MODELS_TOKEN')),

        // Enforced model (do not surface this to end users).
        'model' => env('ASSISTANT_MODEL', env('GITHUB_MODELS_MODEL', 'grok-3')),
        'allow_other_models' => (bool) env('ASSISTANT_ALLOW_OTHER_MODELS', false),

        // Transport
        'timeout_seconds' => (int) env('ASSISTANT_TIMEOUT_SECONDS', 60),
        'connect_timeout_seconds' => (int) env('ASSISTANT_CONNECT_TIMEOUT_SECONDS', 10),

        // API path (OpenAI-compatible). Override if your gateway differs.
        'chat_completions_path' => env('ASSISTANT_CHAT_COMPLETIONS_PATH', '/v1/chat/completions'),

        // Optional extra headers (kept internal). Useful for gateways/proxies.
        // Example: ['X-Foo' => 'bar']
        'headers' => [
            // 'X-Request-Source' => env('ASSISTANT_REQUEST_SOURCE', 'internal'),
        ],
    ],

    'defaults' => [
        // Keep generic; avoid provider/model references.
        'system' => env('ASSISTANT_SYSTEM', 'Be concise and accurate.'),

        // Request defaults (can be overridden per call)
        'temperature' => (float) env('ASSISTANT_TEMPERATURE', 0.2),
        'max_tokens' => env('ASSISTANT_MAX_TOKENS') !== null ? (int) env('ASSISTANT_MAX_TOKENS') : null,

        // Tool calling defaults (OpenAI-compatible). Kept internal.
        // Common values: 'auto', 'none', or a specific tool choice payload.
        'tool_choice' => env('ASSISTANT_TOOL_CHOICE') ?: null,

        // Response format defaults (OpenAI-compatible).
        // Example: ['type' => 'json_object']
        'response_format' => null,
    ],

    'cache' => [
        'enabled' => (bool) env('ASSISTANT_CACHE_ENABLED', true),
        'ttl_seconds' => (int) env('ASSISTANT_CACHE_TTL_SECONDS', 300),

        // Cache key prefix (lets multiple apps share the same cache backend safely)
        'key_prefix' => env('ASSISTANT_CACHE_PREFIX', 'assistant:'),

        // Optional: probabilistic sampling to reduce cache growth.
        // 1.0 = cache everything, 0.0 = cache nothing.
        'sample_rate' => (float) env('ASSISTANT_CACHE_SAMPLE_RATE', 1.0),
    ],

    'retries' => [
        // Total additional retries after the initial attempt.
        'count' => (int) env('ASSISTANT_RETRY_COUNT', 2),

        // Exponential backoff: delay = base * 2^attempt (+ jitter)
        'base_delay_ms' => (int) env('ASSISTANT_RETRY_BASE_DELAY_MS', 250),
        'max_delay_ms' => (int) env('ASSISTANT_RETRY_MAX_DELAY_MS', 2000),
        'jitter_ms' => (int) env('ASSISTANT_RETRY_JITTER_MS', 150),

        // Retry policy (status codes/timeouts). Client/service may interpret this.
        'retry_on_status' => [429, 500, 502, 503, 504],
        'retry_on_connection_errors' => true,
    ],

    'json' => [
        // Additional attempts to repair invalid JSON responses.
        'fix_attempts' => (int) env('ASSISTANT_JSON_FIX_ATTEMPTS', 2),

        // Hard requirement prompt for JSON calls (kept internal).
        'force_json_prompt' => env('ASSISTANT_JSON_FORCE_PROMPT', 'You must reply with ONLY a single valid JSON object. Do not include markdown.'),
    ],

    'logging' => [
        // Keep logs internal-only; never echo provider/model in user outputs.
        'enabled' => (bool) env('ASSISTANT_LOG_ENABLED', true),
        'level' => env('ASSISTANT_LOG_LEVEL', 'debug'),

        // Do not log raw prompts/responses by default (safer for secrets/PII).
        'log_prompts' => (bool) env('ASSISTANT_LOG_PROMPTS', false),
        'log_responses' => (bool) env('ASSISTANT_LOG_RESPONSES', false),

        // Simple redaction list applied by higher-level services (best-effort).
        'redact_keys' => [
            'authorization',
            'token',
            'api_key',
            'password',
            'secret',
        ],
    ],

    'circuit_breaker' => [
        // If enabled, callers may choose to short-circuit after repeated failures.
        'enabled' => (bool) env('ASSISTANT_CB_ENABLED', false),
        'failure_threshold' => (int) env('ASSISTANT_CB_FAILURE_THRESHOLD', 10),
        'cooldown_seconds' => (int) env('ASSISTANT_CB_COOLDOWN_SECONDS', 60),
    ],

    'rate_limit' => [
        // Soft limit knobs for internal usage (implementation optional).
        'enabled' => (bool) env('ASSISTANT_RATE_LIMIT_ENABLED', false),
        'max_per_minute' => (int) env('ASSISTANT_RATE_LIMIT_PER_MINUTE', 60),
    ],
];
