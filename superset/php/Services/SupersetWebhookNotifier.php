<?php

declare(strict_types=1);

namespace App\Services\Superset;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Superset Webhook Notifier
 *
 * Sends webhook notifications for Superset events.
 */
final class SupersetWebhookNotifier
{
    public function __construct(
        private readonly ?string $webhookUrl = null,
        private readonly int $timeout = 10,
        private readonly int $retries = 3
    ) {
    }

    /**
     * Notify about dashboard creation.
     */
    public function notifyDashboardCreated(array $dashboard): bool
    {
        return $this->send('dashboard.created', [
            'dashboard_id' => $dashboard['id'] ?? null,
            'title' => $dashboard['dashboard_title'] ?? null,
            'slug' => $dashboard['slug'] ?? null,
            'created_at' => now()->toIso8601String(),
        ]);
    }

    /**
     * Notify about dashboard update.
     */
    public function notifyDashboardUpdated(array $dashboard): bool
    {
        return $this->send('dashboard.updated', [
            'dashboard_id' => $dashboard['id'] ?? null,
            'title' => $dashboard['dashboard_title'] ?? null,
            'slug' => $dashboard['slug'] ?? null,
            'updated_at' => now()->toIso8601String(),
        ]);
    }

    /**
     * Notify about dashboard deletion.
     */
    public function notifyDashboardDeleted(int $dashboardId): bool
    {
        return $this->send('dashboard.deleted', [
            'dashboard_id' => $dashboardId,
            'deleted_at' => now()->toIso8601String(),
        ]);
    }

    /**
     * Notify about query execution.
     */
    public function notifyQueryExecuted(array $queryResult): bool
    {
        return $this->send('query.executed', [
            'query_id' => $queryResult['query_id'] ?? null,
            'database_id' => $queryResult['database_id'] ?? null,
            'status' => $queryResult['status'] ?? 'unknown',
            'rows' => count($queryResult['data'] ?? []),
            'executed_at' => now()->toIso8601String(),
        ]);
    }

    /**
     * Notify about sync completion.
     */
    public function notifySyncCompleted(array $stats): bool
    {
        return $this->send('sync.completed', [
            'stats' => $stats,
            'completed_at' => now()->toIso8601String(),
        ]);
    }

    /**
     * Notify about export completion.
     */
    public function notifyExportCompleted(array $exportInfo): bool
    {
        return $this->send('export.completed', [
            'dashboard_ids' => $exportInfo['dashboard_ids'] ?? [],
            'output_path' => $exportInfo['output_path'] ?? null,
            'size' => $exportInfo['size'] ?? 0,
            'completed_at' => now()->toIso8601String(),
        ]);
    }

    /**
     * Send generic event notification.
     */
    public function notifyEvent(string $event, array $data): bool
    {
        return $this->send($event, $data);
    }

    /**
     * Send webhook notification with retries.
     */
    private function send(string $event, array $data): bool
    {
        $url = $this->webhookUrl ?? config('superset.webhook.url');

        if (!$url) {
            Log::debug('Webhook URL not configured, skipping notification', [
                'event' => $event,
            ]);
            return false;
        }

        $payload = [
            'event' => $event,
            'data' => $data,
            'timestamp' => now()->toIso8601String(),
            'source' => 'superset-php-client',
        ];

        $attempt = 0;
        $lastError = null;

        while ($attempt < $this->retries) {
            try {
                $response = Http::timeout($this->timeout)
                    ->post($url, $payload);

                if ($response->successful()) {
                    Log::info('Webhook notification sent successfully', [
                        'event' => $event,
                        'attempt' => $attempt + 1,
                    ]);
                    return true;
                }

                $lastError = "HTTP {$response->status()}: {$response->body()}";
            } catch (\Exception $e) {
                $lastError = $e->getMessage();
            }

            $attempt++;

            if ($attempt < $this->retries) {
                // Exponential backoff
                usleep((int) (100000 * pow(2, $attempt)));
            }
        }

        Log::error('Webhook notification failed after retries', [
            'event' => $event,
            'attempts' => $this->retries,
            'last_error' => $lastError,
        ]);

        return false;
    }

    /**
     * Create a new notifier instance.
     */
    public static function make(?string $webhookUrl = null): self
    {
        return new self(
            $webhookUrl,
            config('superset.webhook.timeout', 10),
            config('superset.webhook.retries', 3)
        );
    }
}
