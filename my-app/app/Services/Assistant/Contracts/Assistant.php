<?php

declare(strict_types=1);

namespace App\Services\Assistant\Contracts;

interface Assistant
{
    /**
     * Basic text completion.
     */
    public function text(string $prompt, array $options = []): string;

    /**
     * Structured JSON response.
     *
     * @return array<string, mixed>
     */
    public function json(string $prompt, array $options = []): array;

    /**
     * JSON Schema helper.
     *
     * @param array<string, mixed> $schema
     * @return array<string, mixed>
     */
    public function jsonSchema(string $prompt, array $schema, string $schemaName = 'schema', array $options = []): array;
}
