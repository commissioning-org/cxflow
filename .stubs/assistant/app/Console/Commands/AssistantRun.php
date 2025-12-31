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
        {--schema-file= : Path to a JSON schema file (implies --json)}
        {--schema-name=schema : Schema name used in response_format}
        {--no-cache : Disable caching}
        {--temp=0.2 : Temperature}
        {--max= : Max tokens}
        {--system= : Override system prompt}
    ';

    protected $description = 'Run internal assistant completion (server-side).';

    public function handle(AssistantService $assistant): int
    {
        $prompt = (string) $this->argument('prompt');
        $schemaFile = $this->option('schema-file');
        $asJson = (bool) $this->option('json') || ($schemaFile !== null && $schemaFile !== '');

        $options = [
            'cache_enabled' => !$this->option('no-cache'),
            'temperature' => (float) $this->option('temp'),
            'max_tokens' => $this->option('max') !== null ? (int) $this->option('max') : null,
            'system' => $this->option('system') !== null ? (string) $this->option('system') : null,
        ];

        if ($asJson) {
            if ($schemaFile !== null && $schemaFile !== '') {
                if (!is_string($schemaFile) || !is_file($schemaFile)) {
                    $this->error('Schema file not found.');
                    return self::FAILURE;
                }

                $raw = (string) file_get_contents($schemaFile);
                $schema = json_decode($raw, true);
                if (!is_array($schema)) {
                    $this->error('Schema file is not valid JSON.');
                    return self::FAILURE;
                }

                $schemaName = (string) ($this->option('schema-name') ?? 'schema');
                $data = $assistant->jsonSchema($prompt, $schema, $schemaName, $options);
            } else {
                $data = $assistant->json($prompt, $options);
            }
            $this->line(json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
            return self::SUCCESS;
        }

        $text = $assistant->text($prompt, $options);
        $this->line($text);
        return self::SUCCESS;
    }
}
