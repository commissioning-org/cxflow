<?php

declare(strict_types=1);

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * User API Resource for consistent JSON output.
 *
 * @property \App\Models\User $resource
 */
class UserResource extends JsonResource
{
    /**
     * Transform the resource into an array.
     *
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'name' => $this->name,
            'email' => $this->when(
                $this->shouldShowEmail($request),
                $this->email
            ),
            'phone' => $this->when(
                $this->shouldShowPhone($request),
                $this->phone
            ),
            'avatar_url' => $this->avatar_url,
            'initials' => $this->initials,
            'status' => $this->status,
            'locale' => $this->locale,
            'timezone' => $this->timezone,

            // Computed attributes
            'is_verified' => !is_null($this->email_verified_at),
            'is_admin' => $this->is_admin,
            'has_2fa' => $this->hasTwoFactorEnabled(),
            'member_since' => $this->memberSince(),

            // Relationships
            'roles' => $this->whenLoaded('roles', function () {
                return $this->roles->pluck('name');
            }),

            // Timestamps
            'email_verified_at' => $this->email_verified_at?->toIso8601String(),
            'last_login_at' => $this->last_login_at?->toIso8601String(),
            'created_at' => $this->created_at?->toIso8601String(),
            'updated_at' => $this->updated_at?->toIso8601String(),

            // Links
            'links' => [
                'self' => route('api.users.show', $this->id),
                'activities' => route('api.users.activities', $this->id),
            ],
        ];
    }

    /**
     * Get additional data for the resource.
     *
     * @return array<string, mixed>
     */
    public function with(Request $request): array
    {
        return [
            'meta' => [
                'version' => '1.0',
            ],
        ];
    }

    /**
     * Check if email should be shown.
     */
    protected function shouldShowEmail(Request $request): bool
    {
        $authUser = $request->user();

        // Show to self
        if ($authUser && $authUser->id === $this->id) {
            return true;
        }

        // Check privacy preference
        if (!$this->getPreference('privacy.show_email', false)) {
            return $authUser?->hasPermission('users.view') ?? false;
        }

        return true;
    }

    /**
     * Check if phone should be shown.
     */
    protected function shouldShowPhone(Request $request): bool
    {
        $authUser = $request->user();

        // Show to self
        if ($authUser && $authUser->id === $this->id) {
            return true;
        }

        // Check privacy preference
        if (!$this->getPreference('privacy.show_phone', false)) {
            return $authUser?->hasPermission('users.view') ?? false;
        }

        return true;
    }
}
