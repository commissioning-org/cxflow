<?php

declare(strict_types=1);

return [
    /*
    |--------------------------------------------------------------------------
    | ML Automation (internal)
    |--------------------------------------------------------------------------
    |
    | This configuration powers a fully-automated, server-side ML workflow:
    | ingest -> train -> register -> (optional) promote -> monitor.
    |
    | Nothing here is user-facing. Keep secrets and provider/model details out
    | of public responses. Configure sources via environment variables.
    |
    */

    'enabled' => (bool) env('ML_AUTOMATION_ENABLED', false),

    // Storage (local disk by default). Artifacts are stored under storage/app/ml
    'storage' => [
        'disk' => env('ML_AUTOMATION_STORAGE_DISK', env('FILESYSTEM_DISK', 'local')),
        'base_path' => env('ML_AUTOMATION_STORAGE_PATH', 'ml'),
    ],

    // Dataset ingestion defaults
    'ingest' => [
        // Hard cap to avoid memory blowups from huge CSV/JSON
        'max_rows' => (int) env('ML_AUTOMATION_MAX_ROWS', 5000),
        'timeout_seconds' => (int) env('ML_AUTOMATION_INGEST_TIMEOUT_SECONDS', 30),
        // If true, include raw rows in stored artifacts/webhooks (can be sensitive/large).
        'include_rows' => (bool) env('ML_AUTOMATION_INCLUDE_ROWS', false),
    ],

    // One or more automated pipelines
    'pipelines' => [
        'default' => [
            // Source can be a local file path (absolute or relative to project root),
            // or an http(s) URL returning JSON (array or {rows: [...]})
            'source' => env('ML_AUTOMATION_SOURCE', ''),
            // Optional: csv|json|auto
            'format' => env('ML_AUTOMATION_FORMAT', 'auto'),

            // Training settings (target can be auto-guessed if empty)
            'target' => env('ML_AUTOMATION_TARGET', ''),
            'problem' => env('ML_AUTOMATION_PROBLEM') ?: null,
            'metric' => env('ML_AUTOMATION_METRIC') ?: null,

            // Auto actions
            'auto_promote' => (bool) env('ML_AUTOMATION_AUTO_PROMOTE', true),

            // Internal analysis helpers (uses the internal assistant if available)
            'assistant' => [
                'enabled' => (bool) env('ML_AUTOMATION_ASSISTANT_ENABLED', true),
                'generate_model_card' => (bool) env('ML_AUTOMATION_MODEL_CARD_ENABLED', true),
            ],
        ],
    ],

    // Optional webhook for pipeline events. If disabled/empty, nothing is posted.
    // Falls back to automl.webhook when these are not set.
    'webhook' => [
        'enabled' => (bool) env('ML_AUTOMATION_WEBHOOK_ENABLED', false),
        'url' => (string) env('ML_AUTOMATION_WEBHOOK_URL', ''),
        'timeout_seconds' => (int) env('ML_AUTOMATION_WEBHOOK_TIMEOUT_SECONDS', 15),
        'include_rows' => (bool) env('ML_AUTOMATION_WEBHOOK_INCLUDE_ROWS', false),
    ],
];
