<?php

declare(strict_types=1);

namespace App\Http\Resources;

use App\Models\ApiToken;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * @property ApiToken $resource
 */
final class ApiTokenResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        /** @var ApiToken $token */
        $token = $this->resource;

        return [
            'id' => $token->id,
            'name' => $token->name,
            'abilities' => $token->abilities ?? [],
            'last_used_at' => $token->last_used_at?->toIso8601String(),
            'expires_at' => $token->expires_at?->toIso8601String(),
            'is_expired' => $token->isExpired(),
            'created_at' => $token->created_at?->toIso8601String(),
        ];
    }
}
