<?php

declare(strict_types=1);

namespace App\Services\Automl;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

final class AutomlWebhookNotifier
{
    /**
     * @param array<string, mixed> $payload
     */
    public function notify(string $event, array $payload): void
    {
        /** @var array<string, mixed> $cfg */
        $cfg = (array) config('automl.webhook', []);
        $enabled = (bool) ($cfg['enabled'] ?? false);
        $url = (string) ($cfg['url'] ?? '');
        $timeout = (int) ($cfg['timeout_seconds'] ?? 15);

        // If AutoML webhook isn't configured, fall back to ML automation webhook.
        if (!$enabled || $url === '') {
            /** @var array<string, mixed> $fallback */
            $fallback = (array) config('ml_automation.webhook', []);
            $enabled = (bool) ($fallback['enabled'] ?? false);
            $url = (string) ($fallback['url'] ?? '');
            $timeout = (int) ($fallback['timeout_seconds'] ?? 15);
        }

        if (!$enabled || $url === '') {
            return;
        }

        try {
            Http::timeout($timeout)
                ->acceptJson()
                ->asJson()
                ->post($url, [
                    'event' => $event,
                    'event_version' => 1,
                    'timestamp' => now()->toIso8601String(),
                    'app' => [
                        'name' => (string) config('app.name'),
                        'env' => (string) config('app.env'),
                    ],
                    'data' => $payload,
                ])
                ->throw();
        } catch (\Throwable $e) {
            // Never break app logic because an external webhook is down.
            Log::warning('automl.webhook_failed', [
                'event' => $event,
                'message' => $e->getMessage(),
            ]);
        }
    }
}
