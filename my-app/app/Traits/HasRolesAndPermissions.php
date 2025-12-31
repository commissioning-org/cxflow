<?php

declare(strict_types=1);

namespace App\Traits;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Collection;

/**
 * Trait for models that can have roles and permissions.
 */
trait HasRolesAndPermissions
{
    /**
     * Boot the trait.
     */
    protected static function bootHasRolesAndPermissions(): void
    {
        static::deleting(function ($model) {
            if (method_exists($model, 'roles')) {
                $model->roles()->detach();
            }
            if (method_exists($model, 'permissions')) {
                $model->permissions()->detach();
            }
        });
    }

    /**
     * Check if has any of the given roles.
     */
    public function hasAnyRole(array $roles): bool
    {
        return !empty(array_intersect($roles, $this->getRoleNames()->toArray()));
    }

    /**
     * Check if has all of the given roles.
     */
    public function hasAllRoles(array $roles): bool
    {
        return count(array_intersect($roles, $this->getRoleNames()->toArray())) === count($roles);
    }

    /**
     * Get all role names.
     */
    public function getRoleNames(): Collection
    {
        return Cache::remember(
            $this->getRoleCacheKey(),
            3600,
            fn () => $this->roles()->pluck('name')
        );
    }

    /**
     * Get all permissions through roles.
     */
    public function getAllPermissions(): Collection
    {
        return Cache::remember(
            $this->getPermissionCacheKey(),
            3600,
            function () {
                $rolePermissions = $this->roles()
                    ->with('permissions')
                    ->get()
                    ->pluck('permissions')
                    ->flatten();

                $directPermissions = $this->permissions ?? collect();

                return $rolePermissions->merge($directPermissions)->unique('id');
            }
        );
    }

    /**
     * Get all permission names.
     */
    public function getPermissionNames(): Collection
    {
        return $this->getAllPermissions()->pluck('name');
    }

    /**
     * Check if has any of the given permissions.
     */
    public function hasAnyPermission(array $permissions): bool
    {
        return !empty(array_intersect($permissions, $this->getPermissionNames()->toArray()));
    }

    /**
     * Check if has all of the given permissions.
     */
    public function hasAllPermissions(array $permissions): bool
    {
        return count(array_intersect($permissions, $this->getPermissionNames()->toArray())) === count($permissions);
    }

    /**
     * Get the role cache key.
     */
    protected function getRoleCacheKey(): string
    {
        return sprintf('roles:%s:%s', class_basename($this), $this->getKey());
    }

    /**
     * Get the permission cache key.
     */
    protected function getPermissionCacheKey(): string
    {
        return sprintf('permissions:%s:%s', class_basename($this), $this->getKey());
    }

    /**
     * Forget cached roles and permissions.
     */
    public function forgetRolesAndPermissions(): void
    {
        Cache::forget($this->getRoleCacheKey());
        Cache::forget($this->getPermissionCacheKey());
    }
}
