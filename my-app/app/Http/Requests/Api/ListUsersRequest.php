<?php

declare(strict_types=1);

namespace App\Http\Requests\Api;

use Illuminate\Foundation\Http\FormRequest;

final class ListUsersRequest extends FormRequest
{
    public function authorize(): bool
    {
        // Hook point: policy/permission checks.
        return true;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'q' => ['sometimes', 'string', 'max:200'],
            'status' => ['sometimes', 'string', 'max:50'],
            'role' => ['sometimes', 'string', 'max:100'],
            'include' => ['sometimes', 'string', 'max:200'],
            'sort' => ['sometimes', 'string', 'max:50'],
            'per_page' => ['sometimes', 'integer', 'min:1', 'max:100'],
        ];
    }

    /**
     * @return array<int, string>
     */
    public function includes(): array
    {
        $include = (string) ($this->validated('include') ?? '');
        $parts = array_filter(array_map('trim', explode(',', $include)));

        // Explicit allowlist
        return array_values(array_intersect($parts, ['roles']));
    }
}
