<?php

declare(strict_types=1);

namespace App\Http\Requests\Api;

use Illuminate\Foundation\Http\FormRequest;

final class LoginRequest extends FormRequest
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
            'email' => ['required', 'string', 'email', 'max:255'],
            'password' => ['required', 'string', 'min:1', 'max:255'],

            // Token issuance options
            'token_name' => ['sometimes', 'string', 'max:100'],
            'abilities' => ['sometimes', 'array', 'max:50'],
            'abilities.*' => ['string', 'max:100'],
            'expires_in_days' => ['sometimes', 'integer', 'min:1', 'max:365'],
        ];
    }

    public function tokenName(): string
    {
        $name = (string) ($this->validated('token_name') ?? 'api');
        return trim($name) !== '' ? $name : 'api';
    }

    /**
     * @return list<string>
     */
    public function abilities(): array
    {
        $abilities = $this->validated('abilities');
        if (!is_array($abilities) || $abilities === []) {
            return ['*'];
        }

        $out = [];
        foreach ($abilities as $a) {
            if (is_string($a) && trim($a) !== '') {
                $out[] = trim($a);
            }
        }

        return $out !== [] ? array_values(array_unique($out)) : ['*'];
    }

    public function expiresInDays(): ?int
    {
        $v = $this->validated('expires_in_days');
        return is_int($v) ? $v : null;
    }
}
