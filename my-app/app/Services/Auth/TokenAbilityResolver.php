<?php

declare(strict_types=1);

namespace App\Services\Auth;

use App\Models\User;

final class TokenAbilityResolver
{
    /**
     * Restrict requested abilities to those permitted for this user.
     *
     * @param list<string> $requested
     * @return list<string>
     */
    public function restrict(User $user, array $requested): array
    {
        // Super admins may request wildcard abilities.
        if ($user->hasRole(User::ROLE_SUPER_ADMIN) && in_array('*', $requested, true)) {
            return ['*'];
        }

        $allowed = $this->allowedForUser($user);

        // Never allow wildcard unless super admin.
        $requested = array_values(array_filter($requested, static fn ($a): bool => $a !== '*'));

        $abilities = array_values(array_unique(array_values(array_intersect($requested, $allowed))));

        // If client requested nothing meaningful, default to the user's allowed abilities.
        if ($abilities === []) {
            $abilities = $allowed;
        }

        return $abilities;
    }

    /**
     * Token abilities are intentionally aligned with permission names.
     *
     * @return list<string>
     */
    public function allowedForUser(User $user): array
    {
        // Super admins can do anything.
        if ($user->hasRole(User::ROLE_SUPER_ADMIN)) {
            return ['*'];
        }

        $abilities = [];

        foreach (['api.access', 'assistant.use', 'api.tokens.manage'] as $perm) {
            if ($user->hasPermission($perm)) {
                $abilities[] = $perm;
            }
        }

        // If the user can access the API, at minimum reflect that in token abilities.
        return $abilities !== [] ? $abilities : ['api.access'];
    }
}
