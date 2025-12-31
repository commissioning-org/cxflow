<?php

declare(strict_types=1);

namespace App\Services\MlAutomation;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Internal-only webhook notifier for ML automation events.
 *
 * This is intentionally generic and resilient: webhook failures must never
 * break core app logic.
 */
final class MlWebhookNotifier
{
    /**
     * @param array<string, mixed> $payload
     */
    public function notify(string $event, array $payload): void
    {
        /** @var array<string, mixed> $cfg */
        $cfg = (array) config('ml_automation.webhook', []);

        $enabled = (bool) ($cfg['enabled'] ?? false);
        $url = (string) ($cfg['url'] ?? '');
        $timeout = (int) ($cfg['timeout_seconds'] ?? 15);

        // If ML automation webhook isn't configured, fall back to AutoML webhook.
        if (!$enabled || $url === '') {
            /** @var array<string, mixed> $fallback */
            $fallback = (array) config('automl.webhook', []);
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
            Log::warning('ml_automation.webhook_failed', [
                'event' => $event,
                'message' => $e->getMessage(),
            ]);
        }
    }
}
