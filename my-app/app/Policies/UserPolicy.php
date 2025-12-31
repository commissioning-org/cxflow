<?php

declare(strict_types=1);

namespace App\Policies;

use App\Models\User;
use Illuminate\Auth\Access\HandlesAuthorization;

/**
 * Policy for User model authorization.
 */
class UserPolicy
{
    use HandlesAuthorization;

    /**
     * Perform pre-authorization checks.
     */
    public function before(User $user, string $ability): ?bool
    {
        // Super admins can do anything
        if ($user->hasRole(User::ROLE_SUPER_ADMIN)) {
            return true;
        }

        return null;
    }

    /**
     * Determine whether the user can view any models.
     */
    public function viewAny(User $user): bool
    {
        return $user->hasPermission('users.view');
    }

    /**
     * Determine whether the user can view the model.
     */
    public function view(User $user, User $model): bool
    {
        // Users can view themselves
        if ($user->id === $model->id) {
            return true;
        }

        return $user->hasPermission('users.view');
    }

    /**
     * Determine whether the user can create models.
     */
    public function create(User $user): bool
    {
        return $user->hasPermission('users.create');
    }

    /**
     * Determine whether the user can update the model.
     */
    public function update(User $user, User $model): bool
    {
        // Users can update themselves
        if ($user->id === $model->id) {
            return true;
        }

        // Prevent editing users with higher role levels
        if ($model->hasRole(User::ROLE_SUPER_ADMIN)) {
            return false;
        }

        return $user->hasPermission('users.update');
    }

    /**
     * Determine whether the user can delete the model.
     */
    public function delete(User $user, User $model): bool
    {
        // Cannot delete yourself
        if ($user->id === $model->id) {
            return false;
        }

        // Cannot delete super admins
        if ($model->hasRole(User::ROLE_SUPER_ADMIN)) {
            return false;
        }

        return $user->hasPermission('users.delete');
    }

    /**
     * Determine whether the user can restore the model.
     */
    public function restore(User $user, User $model): bool
    {
        return $user->hasPermission('users.delete');
    }

    /**
     * Determine whether the user can permanently delete the model.
     */
    public function forceDelete(User $user, User $model): bool
    {
        // Only super admins can force delete (handled in before())
        return false;
    }

    /**
     * Determine whether the user can ban/suspend the model.
     */
    public function ban(User $user, User $model): bool
    {
        // Cannot ban yourself
        if ($user->id === $model->id) {
            return false;
        }

        // Cannot ban super admins
        if ($model->hasRole(User::ROLE_SUPER_ADMIN)) {
            return false;
        }

        // Cannot ban users with higher role levels
        if ($this->hasHigherRole($model, $user)) {
            return false;
        }

        return $user->hasPermission('users.ban');
    }

    /**
     * Determine whether the user can impersonate the model.
     */
    public function impersonate(User $user, User $model): bool
    {
        // Cannot impersonate yourself
        if ($user->id === $model->id) {
            return false;
        }

        // Cannot impersonate super admins
        if ($model->hasRole(User::ROLE_SUPER_ADMIN)) {
            return false;
        }

        return $user->hasPermission('users.impersonate');
    }

    /**
     * Determine whether the user can assign roles to the model.
     */
    public function assignRoles(User $user, User $model): bool
    {
        // Cannot modify your own roles
        if ($user->id === $model->id) {
            return false;
        }

        return $user->hasPermission('roles.assign');
    }

    /**
     * Determine whether the user can view the model's activity log.
     */
    public function viewActivity(User $user, User $model): bool
    {
        // Users can view their own activity
        if ($user->id === $model->id) {
            return true;
        }

        return $user->hasPermission('users.view');
    }

    /**
     * Determine whether the user can export user data.
     */
    public function export(User $user, User $model): bool
    {
        // Users can export their own data (GDPR)
        if ($user->id === $model->id) {
            return true;
        }

        return $user->hasPermission('reports.export');
    }

    /**
     * Check if target user has higher role than current user.
     */
    protected function hasHigherRole(User $target, User $current): bool
    {
        $targetLevel = $target->roles()->max('level') ?? 0;
        $currentLevel = $current->roles()->max('level') ?? 0;

        return $targetLevel > $currentLevel;
    }
}
