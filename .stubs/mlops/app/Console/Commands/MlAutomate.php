<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Jobs\RunMlAutomation;
use App\Services\MlAutomation\MlAutomationPipeline;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;

/**
 * Internal-only command to run an end-to-end ML automation pipeline.
 */
final class MlAutomate extends Command
{
    protected $signature = 'ml:automate
        {--pipeline=default : Pipeline name from config}
        {--source= : Override dataset source}
        {--target= : Override target column}
        {--problem= : Override problem type}
        {--metric= : Override metric}
        {--sync : Run in-process (no queue)}
    ';

    protected $description = 'Run the internal ML automation pipeline (ingest -> train -> artifact).';

    public function handle(MlAutomationPipeline $pipeline): int
    {
        $name = (string) $this->option('pipeline');

        $overrides = [];
        if ($this->option('source') !== null) {
            $overrides['source'] = (string) $this->option('source');
        }
        if ($this->option('target') !== null) {
            $overrides['target'] = (string) $this->option('target');
        }
        if ($this->option('problem') !== null) {
            $overrides['problem'] = (string) $this->option('problem');
        }
        if ($this->option('metric') !== null) {
            $overrides['metric'] = (string) $this->option('metric');
        }

        if ((bool) $this->option('sync')) {
            $artifact = $pipeline->run($name, $overrides);
            $this->line(json_encode($artifact, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
            return self::SUCCESS;
        }

        $resultKey = 'ml:result:' . Str::uuid();
        $traceId = Str::uuid();
        Cache::put($resultKey, ['ok' => false, 'pending' => true, 'trace_id' => $traceId], now()->addMinutes(10));
        RunMlAutomation::dispatch($name, $resultKey, $overrides, $traceId);

        $this->line($resultKey);
        return self::SUCCESS;
    }
}
