<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\Assistant\AssistantService;
use Illuminate\Console\Command;

/**
 * Internal-only CLI helper.
 */
final class AssistantRun extends Command
{
    protected $signature = 'assistant:run
        {prompt : The prompt text}
        {--json : Return JSON (best effort)}
        {--no-cache : Disable caching}
        {--temp=0.2 : Temperature}
        {--max= : Max tokens}
    ';

    protected $description = 'Run internal assistant completion (server-side).';

    public function handle(AssistantService $assistant): int
    {
        $prompt = (string) $this->argument('prompt');
        $asJson = (bool) $this->option('json');

        $options = [
            'cache_enabled' => !$this->option('no-cache'),
            'temperature' => (float) $this->option('temp'),
            'max_tokens' => $this->option('max') !== null ? (int) $this->option('max') : null,
        ];

        if ($asJson) {
            $data = $assistant->json($prompt, $options);
            $this->line(json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
            return self::SUCCESS;
        }

        $text = $assistant->text($prompt, $options);
        $this->line($text);
        return self::SUCCESS;
    }
}
