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
        $cfg = (array) config('automl.webhook', []);
        $enabled = (bool) ($cfg['enabled'] ?? false);
        $url = (string) ($cfg['url'] ?? '');
        $timeout = (int) ($cfg['timeout_seconds'] ?? 15);

        if (!$enabled || $url === '') {
            return;
        }

        try {
            Http::timeout($timeout)
                ->acceptJson()
                ->asJson()
                ->post($url, [
                    'event' => $event,
                    'ts' => now()->toIso8601String(),
                    'app' => config('app.name'),
                    'payload' => $payload,
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
