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
    ],
];
