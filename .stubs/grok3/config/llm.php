<?php

declare(strict_types=1);

return [
    /*
    |--------------------------------------------------------------------------
    | LLM Provider (GitHub Models)
    |--------------------------------------------------------------------------
    |
    | This app is wired to call GitHub Models via an OpenAI-compatible endpoint.
    | The "grok-3 only" requirement is enforced by default: if you change the
    | configured model, requests will be rejected.
    |
    */

    'provider' => 'github-models',

    'github_models' => [
        'base_url' => env('GITHUB_MODELS_BASE_URL', 'https://models.inference.ai.azure.com'),
        'token' => env('GITHUB_MODELS_TOKEN'),

        // "grok-3 only" (can be overridden, but the client will enforce unless allow_other_models=true)
        'model' => env('GITHUB_MODELS_MODEL', 'grok-3'),
        'allow_other_models' => (bool) env('GITHUB_MODELS_ALLOW_OTHER_MODELS', false),

        // Safety + defaults
        'timeout_seconds' => (int) env('GITHUB_MODELS_TIMEOUT_SECONDS', 60),

        // Retry configuration for transient errors (429, 5xx)
        'retries' => (int) env('GITHUB_MODELS_RETRIES', 2),
        'retry_base_delay_ms' => (int) env('GITHUB_MODELS_RETRY_BASE_DELAY_MS', 250),
        'retry_max_delay_ms' => (int) env('GITHUB_MODELS_RETRY_MAX_DELAY_MS', 2000),
        'retry_jitter_ms' => (int) env('GITHUB_MODELS_RETRY_JITTER_MS', 150),
    ],
];
