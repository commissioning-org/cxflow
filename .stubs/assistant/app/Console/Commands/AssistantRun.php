<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Jobs\RunAssistantTask;
use App\Services\Assistant\AssistantService;
use Illuminate\Console\Command;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;
use Symfony\Component\Console\Helper\Table;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * Comprehensive internal-only CLI for running AI assistant completions.
 *
 * Features:
 * - Multiple modes: text, json, chat, batch, pipe, workflow, async
 * - Template support with variable substitution
 * - Output formatting (json, table, csv, yaml, plain)
 * - Pipeline/workflow chaining
 * - Dry-run mode for debugging
 * - Context file loading
 * - Progress tracking and timing
 * - Interactive multi-turn chat
 * - Batch processing from file
 * - Async queue dispatch
 */
final class AssistantRun extends Command
{
    protected $signature = 'assistant:run
        {prompt? : The prompt text (omit for pipe/chat/batch modes)}

        {--mode=text : Mode: text, json, chat, batch, pipe, workflow, async}

        {--json : Shortcut for --mode=json}
        {--schema-file= : Path to a JSON schema file (implies --mode=json)}
        {--schema-name=schema : Schema name used in response_format}

        {--no-cache : Disable caching}
        {--temp=0.2 : Temperature}
        {--max= : Max tokens}
        {--system= : Override system prompt}
        {--system-file= : Load system prompt from file}

        {--context-file=* : Load context from file(s) and prepend to prompt}
        {--template= : Use a named prompt template}
        {--var=* : Template variables as key=value pairs}

        {--output=plain : Output format: plain, json, table, csv, yaml}
        {--out-file= : Write output to file instead of stdout}
        {--append : Append to output file instead of overwrite}

        {--batch-file= : File with prompts (one per line or JSON array)}
        {--batch-concurrency=1 : Parallel batch requests (1 = sequential)}
        {--batch-delimiter=\\n : Delimiter for batch output}

        {--workflow-file= : JSON/YAML workflow definition file}
        {--workflow-step= : Run specific step from workflow}

        {--queue= : Queue name for async dispatch}
        {--result-key= : Cache key to store async result}
        {--poll : Poll for async result after dispatch}
        {--poll-timeout=60 : Max seconds to poll for result}
        {--poll-interval=2 : Seconds between poll attempts}

        {--chat-history-file= : File to persist chat history}
        {--chat-max-turns=50 : Max conversation turns}

        {--dry-run : Show what would be sent without calling API}
        {--verbose : Show detailed progress and timing}
        {--quiet : Suppress all output except result}
        {--timing : Show execution timing}
        {--estimate-tokens : Estimate token counts}

        {--validate-output= : JSON schema file to validate output against}
        {--fail-on-invalid : Exit with failure if output validation fails}

        {--retry= : Override retry count}
        {--timeout= : Override timeout seconds}

        {--stdin : Read prompt from stdin (alias for --mode=pipe)}
    ';

    protected $description = 'Run AI assistant completions with advanced automation features.';

    private float $startTime;

    /** @var array<string, mixed> */
    private array $templates = [];

    protected function initialize(InputInterface $input, OutputInterface $output): void
    {
        $this->startTime = microtime(true);
        $this->loadTemplates();
    }

    public function handle(AssistantService $assistant): int
    {
        try {
            $mode = $this->resolveMode();
            $options = $this->buildOptions();

            if ($this->option('dry-run')) {
                return $this->handleDryRun($mode, $options);
            }

            return match ($mode) {
                'text' => $this->handleText($assistant, $options),
                'json' => $this->handleJson($assistant, $options),
                'chat' => $this->handleChat($assistant, $options),
                'batch' => $this->handleBatch($assistant, $options),
                'pipe' => $this->handlePipe($assistant, $options),
                'workflow' => $this->handleWorkflow($assistant, $options),
                'async' => $this->handleAsync($options),
                default => $this->handleText($assistant, $options),
            };
        } catch (\Throwable $e) {
            $this->error("Error: {$e->getMessage()}");
            if ($this->option('verbose')) {
                $this->error($e->getTraceAsString());
            }
            return self::FAILURE;
        } finally {
            if ($this->option('timing')) {
                $this->showTiming();
            }
        }
    }

    // -------------------------------------------------------------------------
    // Mode Resolution
    // -------------------------------------------------------------------------

    private function resolveMode(): string
    {
        if ($this->option('stdin')) {
            return 'pipe';
        }
        if ($this->option('json') || $this->option('schema-file')) {
            return 'json';
        }
        if ($this->option('batch-file')) {
            return 'batch';
        }
        if ($this->option('workflow-file')) {
            return 'workflow';
        }
        if ($this->option('queue')) {
            return 'async';
        }

        $mode = (string) $this->option('mode');
        return in_array($mode, ['text', 'json', 'chat', 'batch', 'pipe', 'workflow', 'async'], true)
            ? $mode
            : 'text';
    }

    // -------------------------------------------------------------------------
    // Options Builder
    // -------------------------------------------------------------------------

    /**
     * @return array<string, mixed>
     */
    private function buildOptions(): array
    {
        $options = [
            'cache_enabled' => !$this->option('no-cache'),
            'temperature' => (float) $this->option('temp'),
            'max_tokens' => $this->option('max') !== null ? (int) $this->option('max') : null,
            'system' => $this->resolveSystemPrompt(),
        ];

        if ($this->option('retry') !== null) {
            $options['retries'] = (int) $this->option('retry');
        }

        if ($this->option('timeout') !== null) {
            $options['timeout_seconds'] = (int) $this->option('timeout');
        }

        return array_filter($options, fn ($v) => $v !== null);
    }

    private function resolveSystemPrompt(): ?string
    {
        $systemFile = $this->option('system-file');
        if ($systemFile !== null && $systemFile !== '') {
            if (!is_string($systemFile) || !is_file($systemFile)) {
                throw new \InvalidArgumentException("System file not found: {$systemFile}");
            }
            return (string) file_get_contents($systemFile);
        }

        $system = $this->option('system');
        return ($system !== null && $system !== '') ? (string) $system : null;
    }

    // -------------------------------------------------------------------------
    // Prompt Resolution
    // -------------------------------------------------------------------------

    private function resolvePrompt(): string
    {
        $prompt = (string) ($this->argument('prompt') ?? '');

        // Template expansion
        $templateName = $this->option('template');
        if ($templateName !== null && $templateName !== '') {
            $prompt = $this->expandTemplate((string) $templateName, $prompt);
        }

        // Variable substitution
        $vars = $this->parseVariables();
        if (!empty($vars)) {
            $prompt = $this->substituteVariables($prompt, $vars);
        }

        // Context file loading
        $contextFiles = (array) $this->option('context-file');
        if (!empty($contextFiles)) {
            $context = $this->loadContextFiles($contextFiles);
            $prompt = $context . "\n\n" . $prompt;
        }

        if ($this->option('estimate-tokens')) {
            $this->estimateTokens($prompt);
        }

        return $prompt;
    }

    /**
     * @param list<string> $files
     */
    private function loadContextFiles(array $files): string
    {
        $parts = [];
        foreach ($files as $file) {
            if (!is_file($file)) {
                throw new \InvalidArgumentException("Context file not found: {$file}");
            }
            $content = (string) file_get_contents($file);
            $ext = pathinfo($file, PATHINFO_EXTENSION);

            // Wrap in code fence for common code files
            if (in_array($ext, ['php', 'js', 'ts', 'py', 'json', 'yaml', 'yml', 'md', 'sql', 'sh', 'bash'], true)) {
                $parts[] = "```{$ext}\n{$content}\n```";
            } else {
                $parts[] = $content;
            }
        }
        return implode("\n\n", $parts);
    }

    /**
     * @return array<string, string>
     */
    private function parseVariables(): array
    {
        $vars = [];
        foreach ((array) $this->option('var') as $pair) {
            if (!is_string($pair)) {
                continue;
            }
            $pos = strpos($pair, '=');
            if ($pos !== false) {
                $key = substr($pair, 0, $pos);
                $value = substr($pair, $pos + 1);
                $vars[$key] = $value;
            }
        }
        return $vars;
    }

    /**
     * @param array<string, string> $vars
     */
    private function substituteVariables(string $text, array $vars): string
    {
        foreach ($vars as $key => $value) {
            $text = str_replace(["{{$key}}", "{{ $key }}", "{{{$key}}}", "{{{ $key }}}"], $value, $text);
        }
        return $text;
    }

    private function loadTemplates(): void
    {
        // Built-in templates
        $this->templates = [
            'summarize' => 'Summarize the following content concisely:\n\n{input}',
            'explain' => 'Explain the following in simple terms:\n\n{input}',
            'translate' => 'Translate the following to {language}:\n\n{input}',
            'code-review' => 'Review the following code for bugs, security issues, and improvements:\n\n{input}',
            'extract-json' => 'Extract structured data from the following as JSON:\n\n{input}',
            'classify' => 'Classify the following into one of these categories: {categories}.\n\nContent:\n{input}',
            'qa' => 'Based on the following context, answer the question.\n\nContext:\n{context}\n\nQuestion: {question}',
            'rewrite' => 'Rewrite the following to be {style}:\n\n{input}',
            'fix-grammar' => 'Fix any grammar and spelling errors in the following:\n\n{input}',
            'generate-tests' => 'Generate unit tests for the following code:\n\n{input}',
        ];

        // Load custom templates from config if available
        $customTemplates = (array) config('assistant.templates', []);
        $this->templates = array_merge($this->templates, $customTemplates);
    }

    private function expandTemplate(string $name, string $input): string
    {
        if (!isset($this->templates[$name])) {
            throw new \InvalidArgumentException("Unknown template: {$name}. Available: " . implode(', ', array_keys($this->templates)));
        }

        $template = $this->templates[$name];
        return str_replace(['{input}', '{ input }'], $input, $template);
    }

    private function estimateTokens(string $text): void
    {
        // Rough estimate: ~4 chars per token for English
        $estimated = (int) ceil(strlen($text) / 4);
        $this->info("Estimated tokens: ~{$estimated}");
    }

    // -------------------------------------------------------------------------
    // Mode Handlers
    // -------------------------------------------------------------------------

    /**
     * @param array<string, mixed> $options
     */
    private function handleText(AssistantService $assistant, array $options): int
    {
        $prompt = $this->resolvePrompt();
        if ($prompt === '') {
            $this->error('No prompt provided.');
            return self::FAILURE;
        }

        $this->verbose("Running text completion...");
        $result = $assistant->text($prompt, $options);
        return $this->outputResult($result);
    }

    /**
     * @param array<string, mixed> $options
     */
    private function handleJson(AssistantService $assistant, array $options): int
    {
        $prompt = $this->resolvePrompt();
        if ($prompt === '') {
            $this->error('No prompt provided.');
            return self::FAILURE;
        }

        $schemaFile = $this->option('schema-file');
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
            $this->verbose("Running JSON schema completion with schema: {$schemaName}");
            $data = $assistant->jsonSchema($prompt, $schema, $schemaName, $options);
        } else {
            $this->verbose("Running JSON completion...");
            $data = $assistant->json($prompt, $options);
        }

        // Validate output if requested
        if (!$this->validateOutput($data)) {
            return self::FAILURE;
        }

        return $this->outputResult($data);
    }

    /**
     * @param array<string, mixed> $options
     */
    private function handleChat(AssistantService $assistant, array $options): int
    {
        $historyFile = $this->option('chat-history-file');
        $maxTurns = (int) ($this->option('chat-max-turns') ?? 50);

        $history = $this->loadChatHistory($historyFile);

        $this->info("Interactive chat mode. Type 'exit' or 'quit' to end.");
        $this->info("Commands: /clear (reset history), /save (save history), /history (show history)");
        $this->newLine();

        $turns = 0;
        while ($turns < $maxTurns) {
            $input = $this->ask('You');
            if ($input === null || in_array(strtolower(trim($input)), ['exit', 'quit', '/exit', '/quit'], true)) {
                break;
            }

            // Handle commands
            if (str_starts_with($input, '/')) {
                $this->handleChatCommand($input, $history, $historyFile);
                continue;
            }

            $history[] = ['role' => 'user', 'content' => $input];

            try {
                // Build messages with history
                $messages = array_merge(
                    [['role' => 'system', 'content' => $options['system'] ?? $this->defaultSystem()]],
                    $history
                );

                $response = $assistant->text($input, array_merge($options, [
                    'messages_override' => $messages,
                ]));

                $history[] = ['role' => 'assistant', 'content' => $response];
                $this->info("Assistant: {$response}");
                $this->newLine();

                $turns++;
            } catch (\Throwable $e) {
                $this->error("Error: {$e->getMessage()}");
            }
        }

        if ($historyFile !== null && $historyFile !== '') {
            $this->saveChatHistory($historyFile, $history);
        }

        return self::SUCCESS;
    }

    /**
     * @param array<array{role:string, content:string}> $history
     */
    private function handleChatCommand(string $command, array &$history, mixed $historyFile): void
    {
        $cmd = strtolower(trim($command));

        if ($cmd === '/clear') {
            $history = [];
            $this->info('Chat history cleared.');
        } elseif ($cmd === '/save' && $historyFile !== null && $historyFile !== '') {
            $this->saveChatHistory((string) $historyFile, $history);
            $this->info('Chat history saved.');
        } elseif ($cmd === '/history') {
            foreach ($history as $i => $msg) {
                $role = ucfirst($msg['role']);
                $content = Str::limit($msg['content'], 100);
                $this->line("[{$i}] {$role}: {$content}");
            }
        } else {
            $this->warn("Unknown command: {$command}");
        }
    }

    /**
     * @return array<array{role:string, content:string}>
     */
    private function loadChatHistory(mixed $file): array
    {
        if ($file === null || $file === '' || !is_string($file) || !is_file($file)) {
            return [];
        }
        $content = (string) file_get_contents($file);
        $decoded = json_decode($content, true);
        return is_array($decoded) ? $decoded : [];
    }

    /**
     * @param array<array{role:string, content:string}> $history
     */
    private function saveChatHistory(string $file, array $history): void
    {
        file_put_contents($file, json_encode($history, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    }

    private function defaultSystem(): string
    {
        return (string) config('assistant.defaults.system', 'Be concise and accurate.');
    }

    /**
     * @param array<string, mixed> $options
     */
    private function handleBatch(AssistantService $assistant, array $options): int
    {
        $batchFile = $this->option('batch-file');
        if ($batchFile === null || $batchFile === '' || !is_string($batchFile) || !is_file($batchFile)) {
            $this->error('Batch file not found.');
            return self::FAILURE;
        }

        $content = (string) file_get_contents($batchFile);
        $prompts = $this->parseBatchFile($content);

        if (empty($prompts)) {
            $this->error('No prompts found in batch file.');
            return self::FAILURE;
        }

        $this->info("Processing {$this->count($prompts)} prompts...");

        $results = [];
        $concurrency = max(1, (int) $this->option('batch-concurrency'));
        $delimiter = $this->option('batch-delimiter') === '\\n' ? "\n" : (string) $this->option('batch-delimiter');

        $isJson = $this->resolveMode() === 'json' || (bool) $this->option('json');
        $progressBar = $this->output->createProgressBar($this->count($prompts));
        $progressBar->start();

        // Process sequentially for now (concurrency would require async/promises)
        foreach ($prompts as $i => $prompt) {
            try {
                if ($isJson) {
                    $result = $assistant->json($prompt, $options);
                } else {
                    $result = $assistant->text($prompt, $options);
                }
                $results[] = ['index' => $i, 'prompt' => Str::limit($prompt, 50), 'result' => $result, 'error' => null];
            } catch (\Throwable $e) {
                $results[] = ['index' => $i, 'prompt' => Str::limit($prompt, 50), 'result' => null, 'error' => $e->getMessage()];
            }
            $progressBar->advance();
        }

        $progressBar->finish();
        $this->newLine(2);

        return $this->outputBatchResults($results, $delimiter);
    }

    /**
     * @return list<string>
     */
    private function parseBatchFile(string $content): array
    {
        // Try JSON array first
        $decoded = json_decode($content, true);
        if (is_array($decoded) && array_is_list($decoded)) {
            return array_map(fn ($x) => is_string($x) ? $x : json_encode($x), $decoded);
        }

        // Fall back to line-by-line
        return array_filter(array_map('trim', explode("\n", $content)), fn ($line) => $line !== '');
    }

    /**
     * @param array<int, array{index:int, prompt:string, result:mixed, error:?string}> $results
     */
    private function outputBatchResults(array $results, string $delimiter): int
    {
        $format = (string) $this->option('output');
        $outFile = $this->option('out-file');

        $output = match ($format) {
            'json' => json_encode($results, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
            'csv' => $this->formatCsv($results),
            'table' => null, // handled separately
            default => implode($delimiter, array_map(fn ($r) => is_array($r['result']) ? json_encode($r['result']) : (string) $r['result'], $results)),
        };

        if ($format === 'table') {
            $this->renderTable(['Index', 'Prompt', 'Result', 'Error'], array_map(fn ($r) => [
                $r['index'],
                Str::limit($r['prompt'], 30),
                Str::limit(is_array($r['result']) ? json_encode($r['result']) : (string) $r['result'], 60),
                $r['error'] ?? '',
            ], $results));
            return self::SUCCESS;
        }

        if ($outFile !== null && $outFile !== '' && is_string($outFile)) {
            $flags = $this->option('append') ? FILE_APPEND : 0;
            file_put_contents($outFile, $output . "\n", $flags);
            $this->info("Output written to: {$outFile}");
        } else {
            $this->line((string) $output);
        }

        $failures = array_filter($results, fn ($r) => $r['error'] !== null);
        if (!empty($failures)) {
            $this->warn("Completed with " . $this->count($failures) . " errors.");
            return self::FAILURE;
        }

        return self::SUCCESS;
    }

    /**
     * @param array<string, mixed> $options
     */
    private function handlePipe(AssistantService $assistant, array $options): int
    {
        $this->verbose("Reading from stdin...");

        $stdin = '';
        $stream = fopen('php://stdin', 'r');
        if ($stream !== false) {
            stream_set_blocking($stream, false);
            $stdin = (string) stream_get_contents($stream);
            fclose($stream);
        }

        if ($stdin === '') {
            // Try argument as fallback
            $stdin = (string) ($this->argument('prompt') ?? '');
        }

        if ($stdin === '') {
            $this->error('No input received from stdin or arguments.');
            return self::FAILURE;
        }

        $isJson = (bool) $this->option('json') || $this->option('schema-file') !== null;
        if ($isJson) {
            $data = $assistant->json($stdin, $options);
            return $this->outputResult($data);
        }

        $result = $assistant->text($stdin, $options);
        return $this->outputResult($result);
    }

    /**
     * @param array<string, mixed> $options
     */
    private function handleWorkflow(AssistantService $assistant, array $options): int
    {
        $workflowFile = $this->option('workflow-file');
        if ($workflowFile === null || $workflowFile === '' || !is_string($workflowFile) || !is_file($workflowFile)) {
            $this->error('Workflow file not found.');
            return self::FAILURE;
        }

        $content = (string) file_get_contents($workflowFile);
        $workflow = $this->parseWorkflowFile($content, $workflowFile);

        if (!is_array($workflow) || empty($workflow['steps'])) {
            $this->error('Invalid workflow file: missing steps.');
            return self::FAILURE;
        }

        $specificStep = $this->option('workflow-step');
        $steps = (array) $workflow['steps'];

        if ($specificStep !== null && $specificStep !== '') {
            $steps = array_filter($steps, fn ($step) => ($step['name'] ?? '') === $specificStep);
            if (empty($steps)) {
                $this->error("Step not found: {$specificStep}");
                return self::FAILURE;
            }
        }

        $this->info("Running workflow: " . ($workflow['name'] ?? 'unnamed'));

        $context = [
            'input' => $this->argument('prompt') ?? '',
            'vars' => $this->parseVariables(),
            'results' => [],
        ];

        foreach ($steps as $i => $step) {
            $stepName = $step['name'] ?? "step_{$i}";
            $this->verbose("Running step: {$stepName}");

            try {
                $context = $this->runWorkflowStep($assistant, $step, $context, $options);
            } catch (\Throwable $e) {
                if ((bool) ($step['continue_on_error'] ?? false)) {
                    $this->warn("Step {$stepName} failed (continuing): {$e->getMessage()}");
                    $context['results'][$stepName] = ['error' => $e->getMessage()];
                } else {
                    throw $e;
                }
            }
        }

        $finalOutput = $context['results'][$this->lastKey($context['results'])] ?? $context['results'];
        return $this->outputResult($finalOutput);
    }

    /**
     * @return array<string, mixed>
     */
    private function parseWorkflowFile(string $content, string $file): array
    {
        $ext = pathinfo($file, PATHINFO_EXTENSION);

        if (in_array($ext, ['yaml', 'yml'], true)) {
            if (!function_exists('yaml_parse')) {
                // Fallback: try basic YAML parsing
                return $this->parseSimpleYaml($content);
            }
            return (array) yaml_parse($content);
        }

        return (array) json_decode($content, true);
    }

    /**
     * @return array<string, mixed>
     */
    private function parseSimpleYaml(string $content): array
    {
        // Very basic YAML-like parsing for simple workflows
        $result = ['steps' => []];
        $lines = explode("\n", $content);

        foreach ($lines as $line) {
            if (preg_match('/^name:\s*(.+)$/', $line, $m)) {
                $result['name'] = trim($m[1]);
            }
        }

        // For proper YAML support, recommend installing yaml extension
        $this->warn('For full YAML support, install the yaml PHP extension.');
        return $result;
    }

    /**
     * @param array<string, mixed> $step
     * @param array<string, mixed> $context
     * @param array<string, mixed> $options
     * @return array<string, mixed>
     */
    private function runWorkflowStep(AssistantService $assistant, array $step, array $context, array $options): array
    {
        $type = $step['type'] ?? 'text';
        $prompt = $this->interpolateWorkflowPrompt((string) ($step['prompt'] ?? ''), $context);
        $stepName = $step['name'] ?? 'unnamed';

        $stepOptions = array_merge($options, [
            'system' => $step['system'] ?? $options['system'] ?? null,
            'temperature' => (float) ($step['temperature'] ?? $options['temperature'] ?? 0.2),
        ]);

        $result = match ($type) {
            'json' => $assistant->json($prompt, $stepOptions),
            'text' => $assistant->text($prompt, $stepOptions),
            'transform' => $this->transformStep($step, $context),
            'condition' => $this->conditionStep($step, $context),
            default => $assistant->text($prompt, $stepOptions),
        };

        $context['results'][$stepName] = $result;
        $context['last_result'] = $result;

        return $context;
    }

    /**
     * @param array<string, mixed> $context
     */
    private function interpolateWorkflowPrompt(string $prompt, array $context): string
    {
        // Replace {{input}}, {{results.stepName}}, {{vars.key}}, {{last_result}}
        $prompt = str_replace(['{{input}}', '{{ input }}'], (string) $context['input'], $prompt);
        $prompt = str_replace(['{{last_result}}', '{{ last_result }}'], json_encode($context['last_result'] ?? ''), $prompt);

        // {{results.stepName}}
        if (preg_match_all('/\{\{\s*results\.(\w+)\s*\}\}/', $prompt, $matches)) {
            foreach ($matches[1] as $i => $key) {
                $value = $context['results'][$key] ?? '';
                $prompt = str_replace($matches[0][$i], is_array($value) ? json_encode($value) : (string) $value, $prompt);
            }
        }

        // {{vars.key}}
        if (preg_match_all('/\{\{\s*vars\.(\w+)\s*\}\}/', $prompt, $matches)) {
            foreach ($matches[1] as $i => $key) {
                $value = $context['vars'][$key] ?? '';
                $prompt = str_replace($matches[0][$i], (string) $value, $prompt);
            }
        }

        return $prompt;
    }

    /**
     * @param array<string, mixed> $step
     * @param array<string, mixed> $context
     * @return mixed
     */
    private function transformStep(array $step, array $context): mixed
    {
        $source = $step['source'] ?? 'last_result';
        $data = $context[$source] ?? $context['last_result'] ?? null;

        $transform = $step['transform'] ?? null;
        if ($transform === null) {
            return $data;
        }

        return match ($transform) {
            'json_encode' => json_encode($data),
            'json_decode' => is_string($data) ? json_decode($data, true) : $data,
            'uppercase' => strtoupper((string) $data),
            'lowercase' => strtolower((string) $data),
            'trim' => trim((string) $data),
            'extract_json' => $this->extractJson((string) $data),
            default => $data,
        };
    }

    /**
     * @param array<string, mixed> $step
     * @param array<string, mixed> $context
     * @return mixed
     */
    private function conditionStep(array $step, array $context): mixed
    {
        $condition = $step['condition'] ?? '';
        $then = $step['then'] ?? null;
        $else = $step['else'] ?? null;

        // Simple condition evaluation
        $conditionMet = $this->evaluateCondition($condition, $context);

        return $conditionMet ? $then : $else;
    }

    /**
     * @param array<string, mixed> $context
     */
    private function evaluateCondition(string $condition, array $context): bool
    {
        // Very simple condition: "last_result contains 'error'" or "results.step1 == 'success'"
        if (str_contains($condition, 'contains')) {
            preg_match('/(\w+)\s+contains\s+[\'"]([^\'"]+)[\'"]/', $condition, $m);
            if (!empty($m)) {
                $source = $context[$m[1]] ?? '';
                return str_contains((string) (is_array($source) ? json_encode($source) : $source), $m[2]);
            }
        }

        if (str_contains($condition, '==')) {
            preg_match('/(\w+)\s*==\s*[\'"]([^\'"]+)[\'"]/', $condition, $m);
            if (!empty($m)) {
                $source = $context[$m[1]] ?? '';
                return ((string) $source) === $m[2];
            }
        }

        return false;
    }

    /**
     * @return array<string, mixed>|null
     */
    private function extractJson(string $text): ?array
    {
        $text = trim($text);
        $start = strpos($text, '{');
        $end = strrpos($text, '}');
        if ($start !== false && $end !== false && $end > $start) {
            $json = substr($text, $start, $end - $start + 1);
            $decoded = json_decode($json, true);
            if (is_array($decoded)) {
                return $decoded;
            }
        }
        return null;
    }

    /**
     * @param array<string, mixed> $options
     */
    private function handleAsync(array $options): int
    {
        $prompt = $this->resolvePrompt();
        if ($prompt === '') {
            $this->error('No prompt provided.');
            return self::FAILURE;
        }

        $queue = (string) ($this->option('queue') ?? 'default');
        $resultKey = (string) ($this->option('result-key') ?? 'assistant:result:' . Str::uuid());
        $isJson = (bool) $this->option('json');

        $job = new RunAssistantTask(
            task: $isJson ? 'json' : 'text',
            payload: ['prompt' => $prompt],
            resultKey: $resultKey,
            options: $options,
        );

        dispatch($job)->onQueue($queue);

        $this->info("Job dispatched to queue: {$queue}");
        $this->info("Result key: {$resultKey}");

        if ($this->option('poll')) {
            return $this->pollForResult($resultKey);
        }

        // Output the result key for callers to use
        $this->line(json_encode(['queued' => true, 'result_key' => $resultKey]));
        return self::SUCCESS;
    }

    private function pollForResult(string $resultKey): int
    {
        $timeout = (int) ($this->option('poll-timeout') ?? 60);
        $interval = (int) ($this->option('poll-interval') ?? 2);
        $elapsed = 0;

        $this->info("Polling for result (timeout: {$timeout}s)...");

        while ($elapsed < $timeout) {
            $result = Cache::get($resultKey);
            if ($result !== null && is_array($result)) {
                if ((bool) ($result['ok'] ?? false)) {
                    return $this->outputResult($result['result'] ?? $result);
                } else {
                    $this->error("Job failed: " . ($result['error'] ?? 'Unknown error'));
                    return self::FAILURE;
                }
            }

            sleep($interval);
            $elapsed += $interval;
            $this->verbose("Still waiting... ({$elapsed}s)");
        }

        $this->error("Timeout waiting for result.");
        return self::FAILURE;
    }

    // -------------------------------------------------------------------------
    // Dry Run
    // -------------------------------------------------------------------------

    /**
     * @param array<string, mixed> $options
     */
    private function handleDryRun(string $mode, array $options): int
    {
        $prompt = $this->resolvePrompt();

        $payload = [
            'mode' => $mode,
            'prompt' => $prompt,
            'prompt_length' => strlen($prompt),
            'estimated_tokens' => (int) ceil(strlen($prompt) / 4),
            'options' => $options,
        ];

        if ($this->option('schema-file')) {
            $payload['schema_file'] = $this->option('schema-file');
        }

        $this->info("=== DRY RUN ===");
        $this->line(json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    // -------------------------------------------------------------------------
    // Output Handling
    // -------------------------------------------------------------------------

    /**
     * @param mixed $result
     */
    private function outputResult(mixed $result): int
    {
        $format = (string) $this->option('output');
        $outFile = $this->option('out-file');

        $output = match ($format) {
            'json' => json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
            'yaml' => $this->toYaml($result),
            'csv' => $this->toCsv($result),
            'table' => null, // handled separately
            default => is_array($result) ? json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) : (string) $result,
        };

        if ($format === 'table' && is_array($result)) {
            $this->renderArrayAsTable($result);
            return self::SUCCESS;
        }

        if ($outFile !== null && $outFile !== '' && is_string($outFile)) {
            $flags = $this->option('append') ? FILE_APPEND : 0;
            file_put_contents($outFile, $output . "\n", $flags);
            if (!$this->option('quiet')) {
                $this->info("Output written to: {$outFile}");
            }
        } else {
            $this->line((string) $output);
        }

        return self::SUCCESS;
    }

    /**
     * @param mixed $data
     */
    private function toYaml(mixed $data): string
    {
        if (function_exists('yaml_emit')) {
            return yaml_emit($data);
        }

        // Simple fallback for basic structures
        return $this->simpleYamlEncode($data, 0);
    }

    private function simpleYamlEncode(mixed $data, int $indent): string
    {
        $prefix = str_repeat('  ', $indent);

        if (is_null($data)) {
            return 'null';
        }
        if (is_bool($data)) {
            return $data ? 'true' : 'false';
        }
        if (is_int($data) || is_float($data)) {
            return (string) $data;
        }
        if (is_string($data)) {
            if (str_contains($data, "\n") || str_contains($data, ':') || str_contains($data, '#')) {
                return '"' . addslashes($data) . '"';
            }
            return $data;
        }
        if (is_array($data)) {
            if (empty($data)) {
                return array_is_list($data) ? '[]' : '{}';
            }

            $lines = [];
            if (array_is_list($data)) {
                foreach ($data as $item) {
                    $lines[] = $prefix . '- ' . $this->simpleYamlEncode($item, $indent + 1);
                }
            } else {
                foreach ($data as $key => $value) {
                    if (is_array($value) && !empty($value)) {
                        $lines[] = $prefix . $key . ':';
                        $lines[] = $this->simpleYamlEncode($value, $indent + 1);
                    } else {
                        $lines[] = $prefix . $key . ': ' . $this->simpleYamlEncode($value, $indent);
                    }
                }
            }
            return implode("\n", $lines);
        }

        return (string) $data;
    }

    /**
     * @param mixed $data
     */
    private function toCsv(mixed $data): string
    {
        if (!is_array($data)) {
            return (string) $data;
        }

        // If it's a list of associative arrays, create proper CSV
        if (array_is_list($data) && !empty($data) && is_array($data[0])) {
            $lines = [];
            $headers = array_keys($data[0]);
            $lines[] = implode(',', array_map(fn ($h) => '"' . str_replace('"', '""', $h) . '"', $headers));

            foreach ($data as $row) {
                $values = array_map(function ($v) {
                    if (is_array($v)) {
                        $v = json_encode($v);
                    }
                    return '"' . str_replace('"', '""', (string) $v) . '"';
                }, array_values($row));
                $lines[] = implode(',', $values);
            }

            return implode("\n", $lines);
        }

        // Simple key-value
        $lines = [];
        foreach ($data as $key => $value) {
            if (is_array($value)) {
                $value = json_encode($value);
            }
            $lines[] = '"' . str_replace('"', '""', (string) $key) . '","' . str_replace('"', '""', (string) $value) . '"';
        }
        return implode("\n", $lines);
    }

    /**
     * @param array<int, array<int, mixed>> $rows
     */
    private function formatCsv(array $rows): string
    {
        if (empty($rows)) {
            return '';
        }

        $firstRow = $rows[0];
        $headers = array_keys($firstRow);
        $lines = [implode(',', array_map(fn ($h) => '"' . str_replace('"', '""', $h) . '"', $headers))];

        foreach ($rows as $row) {
            $values = array_map(function ($v) {
                if (is_array($v)) {
                    $v = json_encode($v);
                }
                return '"' . str_replace('"', '""', (string) ($v ?? '')) . '"';
            }, array_values($row));
            $lines[] = implode(',', $values);
        }

        return implode("\n", $lines);
    }

    /**
     * @param array<string, mixed> $data
     */
    private function renderArrayAsTable(array $data): void
    {
        if (array_is_list($data) && !empty($data) && is_array($data[0])) {
            $headers = array_keys($data[0]);
            $rows = array_map(fn ($row) => array_map(fn ($v) => is_array($v) ? json_encode($v) : (string) $v, array_values($row)), $data);
            $this->renderTable($headers, $rows);
        } else {
            $rows = [];
            foreach ($data as $key => $value) {
                $rows[] = [(string) $key, is_array($value) ? json_encode($value) : (string) $value];
            }
            $this->renderTable(['Key', 'Value'], $rows);
        }
    }

    /**
     * @param list<string> $headers
     * @param list<list<string>> $rows
     */
    private function renderTable(array $headers, array $rows): void
    {
        $table = new Table($this->output);
        $table->setHeaders($headers);
        $table->setRows($rows);
        $table->render();
    }

    // -------------------------------------------------------------------------
    // Validation
    // -------------------------------------------------------------------------

    /**
     * @param mixed $data
     */
    private function validateOutput(mixed $data): bool
    {
        $validateSchemaFile = $this->option('validate-output');
        if ($validateSchemaFile === null || $validateSchemaFile === '') {
            return true;
        }

        if (!is_string($validateSchemaFile) || !is_file($validateSchemaFile)) {
            $this->warn("Validation schema file not found: {$validateSchemaFile}");
            return true;
        }

        // Basic JSON Schema validation (simplified)
        $schema = json_decode((string) file_get_contents($validateSchemaFile), true);
        if (!is_array($schema)) {
            $this->warn("Invalid validation schema.");
            return true;
        }

        $errors = $this->validateAgainstSchema($data, $schema);
        if (!empty($errors)) {
            $this->error("Output validation failed:");
            foreach ($errors as $error) {
                $this->error("  - {$error}");
            }

            if ($this->option('fail-on-invalid')) {
                return false;
            }
        }

        return true;
    }

    /**
     * @param mixed $data
     * @param array<string, mixed> $schema
     * @return list<string>
     */
    private function validateAgainstSchema(mixed $data, array $schema): array
    {
        $errors = [];

        // Very basic validation
        $type = $schema['type'] ?? null;
        if ($type !== null) {
            $actualType = $this->getJsonType($data);
            if ($type !== $actualType) {
                $errors[] = "Expected type '{$type}', got '{$actualType}'";
            }
        }

        // Required properties check
        if (is_array($data) && isset($schema['required'])) {
            foreach ((array) $schema['required'] as $required) {
                if (!array_key_exists($required, $data)) {
                    $errors[] = "Missing required property: {$required}";
                }
            }
        }

        return $errors;
    }

    private function getJsonType(mixed $value): string
    {
        if (is_null($value)) {
            return 'null';
        }
        if (is_bool($value)) {
            return 'boolean';
        }
        if (is_int($value) || is_float($value)) {
            return 'number';
        }
        if (is_string($value)) {
            return 'string';
        }
        if (is_array($value)) {
            return array_is_list($value) ? 'array' : 'object';
        }
        return 'unknown';
    }

    // -------------------------------------------------------------------------
    // Utilities
    // -------------------------------------------------------------------------

    private function verbose(string $message): void
    {
        if ($this->option('verbose') && !$this->option('quiet')) {
            $elapsed = round((microtime(true) - $this->startTime) * 1000);
            $this->info("[{$elapsed}ms] {$message}");
        }
    }

    private function showTiming(): void
    {
        $total = round((microtime(true) - $this->startTime) * 1000, 2);
        $this->info("Total time: {$total}ms");
    }

    /**
     * @param array<mixed> $arr
     */
    private function count(array $arr): int
    {
        return count($arr);
    }

    /**
     * @param array<string, mixed> $arr
     */
    private function lastKey(array $arr): string|int|null
    {
        if (empty($arr)) {
            return null;
        }
        $keys = array_keys($arr);
        return $keys[count($keys) - 1];
    }
}
