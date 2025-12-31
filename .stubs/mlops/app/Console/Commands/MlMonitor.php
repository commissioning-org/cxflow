<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\MlAutomation\MlWebhookNotifier;
use Illuminate\Console\Command;

/**
 * Lightweight monitoring heartbeat.
 *
 * In production you would extend this to compute drift from live data.
 */
final class MlMonitor extends Command
{
    protected $signature = 'ml:monitor';

    protected $description = 'Emit ML automation heartbeat / monitoring event (internal).';

    public function handle(MlWebhookNotifier $webhook): int
    {
        $webhook->notify('ml.monitor.heartbeat', [
            'ts' => now()->toIso8601String(),
        ]);

        $this->info('ok');
        return self::SUCCESS;
    }
}
