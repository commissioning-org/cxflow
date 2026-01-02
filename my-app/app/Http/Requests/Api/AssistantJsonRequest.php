<?php

declare(strict_types=1);

namespace App\Http\Requests\Api;

use Illuminate\Foundation\Http\FormRequest;

final class AssistantJsonRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'prompt' => ['required', 'string', 'min:1', 'max:12000'],
            'options' => ['sometimes', 'array'],
            'options.model' => ['sometimes', 'string', 'max:200'],
            'options.temperature' => ['sometimes', 'numeric', 'min:0', 'max:2'],
            'options.max_tokens' => ['sometimes', 'integer', 'min:1', 'max:8192'],
            'options.cache_enabled' => ['sometimes', 'boolean'],
            'options.cache_ttl_seconds' => ['sometimes', 'integer', 'min:0', 'max:86400'],
            'options.json_fix_attempts' => ['sometimes', 'integer', 'min:0', 'max:5'],
        ];
    }

    /**
     * @return array<string, mixed>
     */
    public function options(): array
    {
        /** @var array<string, mixed> $options */
        $options = $this->validated('options') ?? [];
        return $options;
    }
}
