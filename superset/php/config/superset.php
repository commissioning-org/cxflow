<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Superset Base URL
    |--------------------------------------------------------------------------
    |
    | The base URL of your Apache Superset instance. This should include
    | the protocol and port if needed (e.g., http://localhost:8088).
    |
    */

    'base_url' => env('SUPERSET_URL', 'http://localhost:8088'),

    /*
    |--------------------------------------------------------------------------
    | Superset Authentication
    |--------------------------------------------------------------------------
    |
    | Credentials for authenticating with Superset. This user should have
    | appropriate permissions for the operations you want to perform.
    |
    */

    'username' => env('SUPERSET_USERNAME', 'admin'),
    'password' => env('SUPERSET_PASSWORD', 'admin'),

    /*
    |--------------------------------------------------------------------------
    | SSL Verification
    |--------------------------------------------------------------------------
    |
    | Whether to verify SSL certificates when connecting to Superset.
    | Set to false for self-signed certificates in development.
    |
    */

    'verify_ssl' => env('SUPERSET_VERIFY_SSL', true),

    /*
    |--------------------------------------------------------------------------
    | Token Cache Duration
    |--------------------------------------------------------------------------
    |
    | How long to cache authentication tokens (in minutes).
    |
    */

    'token_cache_duration' => env('SUPERSET_TOKEN_CACHE', 30),

    /*
    |--------------------------------------------------------------------------
    | Default Query Settings
    |--------------------------------------------------------------------------
    |
    | Default settings for SQL Lab queries.
    |
    */

    'query' => [
        'limit' => env('SUPERSET_QUERY_LIMIT', 1000),
        'timeout' => env('SUPERSET_QUERY_TIMEOUT', 300),
    ],

    /*
    |--------------------------------------------------------------------------
    | Embedding Settings
    |--------------------------------------------------------------------------
    |
    | Settings for embedded dashboards.
    |
    */

    'embedding' => [
        'allowed_domains' => array_filter(explode(',', env('SUPERSET_ALLOWED_DOMAINS', ''))),
        'guest_token_expiry' => env('SUPERSET_GUEST_TOKEN_EXPIRY', 300),
    ],

    /*
    |--------------------------------------------------------------------------
    | Webhook Settings
    |--------------------------------------------------------------------------
    |
    | Configuration for webhook notifications.
    |
    */

    'webhook' => [
        'url' => env('SUPERSET_WEBHOOK_URL'),
        'enabled' => env('SUPERSET_WEBHOOK_ENABLED', false),
        'timeout' => env('SUPERSET_WEBHOOK_TIMEOUT', 10),
        'retries' => env('SUPERSET_WEBHOOK_RETRIES', 3),
    ],

    /*
    |--------------------------------------------------------------------------
    | Sync Settings
    |--------------------------------------------------------------------------
    |
    | Configuration for resource synchronization.
    |
    */

    'sync' => [
        'enabled' => env('SUPERSET_SYNC_ENABLED', true),
        'schedule' => env('SUPERSET_SYNC_SCHEDULE', 'hourly'), // hourly, daily, weekly
        'full_sync_on_startup' => env('SUPERSET_FULL_SYNC_ON_STARTUP', false),
    ],

    /*
    |--------------------------------------------------------------------------
    | Retry Settings
    |--------------------------------------------------------------------------
    |
    | Configuration for API request retries.
    |
    */

    'retry' => [
        'max_attempts' => env('SUPERSET_RETRY_MAX_ATTEMPTS', 3),
        'backoff_multiplier' => env('SUPERSET_RETRY_BACKOFF', 2),
    ],

    /*
    |--------------------------------------------------------------------------
    | Rate Limiting
    |--------------------------------------------------------------------------
    |
    | Configuration for API rate limiting.
    |
    */

    'rate_limit' => [
        'enabled' => env('SUPERSET_RATE_LIMIT_ENABLED', false),
        'max_requests' => env('SUPERSET_RATE_LIMIT_MAX', 100),
        'per_minutes' => env('SUPERSET_RATE_LIMIT_MINUTES', 1),
    ],

];
