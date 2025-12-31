<?php

declare(strict_types=1);

return [
    /*
    |--------------------------------------------------------------------------
    | AutoML Service (internal)
    |--------------------------------------------------------------------------
    |
    | This is an internal service used to train simple models automatically.
    | Keep it behind the backend; do not expose service details to end users.
    |
    */

    'base_url' => env('AUTOML_BASE_URL', 'http://ml:8000'),

    'timeout_seconds' => (int) env('AUTOML_TIMEOUT_SECONDS', 60),

    // Optional webhook (Power Automate, etc.)
    // Keep URL out of git; set via environment/Codespaces secrets.
    'webhook' => [
        'enabled' => (bool) env('AUTOML_WEBHOOK_ENABLED', false),
        'url' => env('AUTOML_WEBHOOK_URL'),
        'timeout_seconds' => (int) env('AUTOML_WEBHOOK_TIMEOUT_SECONDS', 15),

        // If true, includes raw rows in webhook payloads (can be sensitive/large).
        'include_rows' => (bool) env('AUTOML_WEBHOOK_INCLUDE_ROWS', false),

        // Always include a small sample (safer than full rows for Power Automate).
        'sample_rows' => (int) env('AUTOML_WEBHOOK_SAMPLE_ROWS', 50),

        // For predictions, include only the first N in webhook payload.
        'sample_predictions' => (int) env('AUTOML_WEBHOOK_SAMPLE_PREDICTIONS', 200),
    ],
];
