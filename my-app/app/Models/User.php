<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Contracts\Auth\MustVerifyEmail;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Prunable;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\SoftDeletes;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

/**
 * Enhanced User Model with comprehensive features.
 *
 * Features:
 * - Role-based access control (RBAC)
 * - Two-factor authentication support
 * - Activity tracking and audit logging
 * - Profile management with avatars
 * - Preferences and settings
 * - API token management
 * - Social authentication
 * - Soft deletes with pruning
 * - Advanced query scopes
 * - Caching layer
 * - Event dispatching
 *
 * @property int $id
 * @property string $name
 * @property string $email
 * @property string|null $phone
 * @property string|null $avatar
 * @property string $password
 * @property string|null $two_factor_secret
 * @property string|null $two_factor_recovery_codes
 * @property Carbon|null $two_factor_confirmed_at
 * @property Carbon|null $email_verified_at
 * @property Carbon|null $phone_verified_at
 * @property Carbon|null $last_login_at
 * @property string|null $last_login_ip
 * @property string $status
 * @property string $locale
 * @property string $timezone
 * @property array $preferences
 * @property array $metadata
 * @property string|null $remember_token
 * @property Carbon $created_at
 * @property Carbon $updated_at
 * @property Carbon|null $deleted_at
 */
class User extends Authenticatable implements MustVerifyEmail
{
    use HasFactory;
    use Notifiable;
    use SoftDeletes;
    use Prunable;

    // =========================================================================
    // Constants
    // =========================================================================

    /** User status constants */
    public const STATUS_PENDING = 'pending';
    public const STATUS_ACTIVE = 'active';
    public const STATUS_SUSPENDED = 'suspended';
    public const STATUS_BANNED = 'banned';

    /** Role constants */
    public const ROLE_USER = 'user';
    public const ROLE_MODERATOR = 'moderator';
    public const ROLE_ADMIN = 'admin';
    public const ROLE_SUPER_ADMIN = 'super_admin';

    /** Cache TTL in seconds */
    protected const CACHE_TTL = 3600;

    // =========================================================================
    // Model Configuration
    // =========================================================================

    /**
     * The attributes that are mass assignable.
     *
     * @var list<string>
     */
    protected $fillable = [
        'name',
        'email',
        'phone',
        'password',
        'avatar',
        'status',
        'locale',
        'timezone',
        'preferences',
        'metadata',
        'last_login_at',
        'last_login_ip',
    ];

    /**
     * The attributes that should be hidden for serialization.
     *
     * @var list<string>
     */
    protected $hidden = [
        'password',
        'remember_token',
        'two_factor_secret',
        'two_factor_recovery_codes',
    ];

    /**
     * The attributes that should be appended to arrays.
     *
     * @var list<string>
     */
    protected $appends = [
        'avatar_url',
        'initials',
        'is_admin',
        'full_name',
    ];

    /**
     * The model's default values for attributes.
     *
     * @var array<string, mixed>
     */
    protected $attributes = [
        'status' => self::STATUS_PENDING,
        'locale' => 'en',
        'timezone' => 'UTC',
        'preferences' => '{}',
        'metadata' => '{}',
    ];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'email_verified_at' => 'datetime',
            'phone_verified_at' => 'datetime',
            'two_factor_confirmed_at' => 'datetime',
            'last_login_at' => 'datetime',
            'password' => 'hashed',
            'preferences' => 'array',
            'metadata' => 'array',
        ];
    }

    /**
     * The "booted" method of the model.
     */
    protected static function booted(): void
    {
        // Generate UUID on creation
        static::creating(function (User $user) {
            if (empty($user->preferences)) {
                $user->preferences = self::defaultPreferences();
            }
        });

        // Clear cache on update
        static::updated(function (User $user) {
            $user->clearCache();
        });

        // Clean up on delete
        static::deleting(function (User $user) {
            $user->clearCache();
            // Optionally delete avatar
            if ($user->avatar && !$user->isForceDeleting()) {
                // Keep avatar for soft deletes
            }
        });
    }

    // =========================================================================
    // Relationships
    // =========================================================================

    /**
     * The roles that belong to the user.
     */
    public function roles(): BelongsToMany
    {
        return $this->belongsToMany(Role::class, 'user_roles')
            ->withTimestamps()
            ->withPivot(['assigned_by', 'expires_at']);
    }

    /**
     * The permissions directly assigned to the user.
     */
    public function permissions(): BelongsToMany
    {
        return $this->belongsToMany(Permission::class, 'user_permissions')
            ->withTimestamps();
    }

    /**
     * Get the user's activity logs.
     */
    public function activities(): HasMany
    {
        return $this->hasMany(Activity::class)->latest();
    }

    /**
     * Get the user's API tokens.
     */
    public function apiTokens(): HasMany
    {
        return $this->hasMany(ApiToken::class);
    }

    /**
     * Get the user's social accounts.
     */
    public function socialAccounts(): HasMany
    {
        return $this->hasMany(SocialAccount::class);
    }

    /**
     * Get the user's notifications.
     */
    public function notifications(): HasMany
    {
        return $this->hasMany(Notification::class)->latest();
    }

    /**
     * Get the user's login history.
     */
    public function loginHistory(): HasMany
    {
        return $this->hasMany(LoginHistory::class)->latest();
    }

    // =========================================================================
    // Accessors & Mutators (Laravel 11+ Attribute Style)
    // =========================================================================

    /**
     * Get the user's avatar URL.
     */
    protected function avatarUrl(): Attribute
    {
        return Attribute::make(
            get: function (): string {
                if ($this->avatar) {
                    if (Str::startsWith($this->avatar, ['http://', 'https://'])) {
                        return $this->avatar;
                    }
                    return Storage::disk('public')->url($this->avatar);
                }
                
                // Gravatar fallback
                $hash = md5(strtolower(trim($this->email)));
                return "https://www.gravatar.com/avatar/{$hash}?d=mp&s=200";
            },
        );
    }

    /**
     * Get the user's initials.
     */
    protected function initials(): Attribute
    {
        return Attribute::make(
            get: function (): string {
                $words = explode(' ', trim($this->name));
                $initials = '';
                
                foreach (array_slice($words, 0, 2) as $word) {
                    $initials .= strtoupper(substr($word, 0, 1));
                }
                
                return $initials ?: '??';
            },
        );
    }

    /**
     * Get the user's full name (with title if available).
     */
    protected function fullName(): Attribute
    {
        return Attribute::make(
            get: fn (): string => trim(($this->metadata['title'] ?? '') . ' ' . $this->name),
        );
    }

    /**
     * Check if user is an admin.
     */
    protected function isAdmin(): Attribute
    {
        return Attribute::make(
            get: fn (): bool => $this->hasRole([self::ROLE_ADMIN, self::ROLE_SUPER_ADMIN]),
        );
    }

    /**
     * Get/set the user's first name.
     */
    protected function firstName(): Attribute
    {
        return Attribute::make(
            get: fn (): string => explode(' ', $this->name)[0] ?? '',
            set: fn (string $value): array => [
                'name' => $value . ' ' . $this->lastName,
            ],
        );
    }

    /**
     * Get/set the user's last name.
     */
    protected function lastName(): Attribute
    {
        return Attribute::make(
            get: function (): string {
                $parts = explode(' ', $this->name);
                return count($parts) > 1 ? end($parts) : '';
            },
        );
    }

    // =========================================================================
    // Query Scopes
    // =========================================================================

    /**
     * Scope: Only active users.
     */
    public function scopeActive(Builder $query): Builder
    {
        return $query->where('status', self::STATUS_ACTIVE);
    }

    /**
     * Scope: Only verified users.
     */
    public function scopeVerified(Builder $query): Builder
    {
        return $query->whereNotNull('email_verified_at');
    }

    /**
     * Scope: Only unverified users.
     */
    public function scopeUnverified(Builder $query): Builder
    {
        return $query->whereNull('email_verified_at');
    }

    /**
     * Scope: Users with specific status.
     */
    public function scopeWithStatus(Builder $query, string $status): Builder
    {
        return $query->where('status', $status);
    }

    /**
     * Scope: Users with specific role.
     */
    public function scopeWithRole(Builder $query, string $role): Builder
    {
        return $query->whereHas('roles', fn ($q) => $q->where('name', $role));
    }

    /**
     * Scope: Users created within date range.
     */
    public function scopeCreatedBetween(Builder $query, Carbon $start, Carbon $end): Builder
    {
        return $query->whereBetween('created_at', [$start, $end]);
    }

    /**
     * Scope: Recently active users.
     */
    public function scopeRecentlyActive(Builder $query, int $days = 7): Builder
    {
        return $query->where('last_login_at', '>=', now()->subDays($days));
    }

    /**
     * Scope: Inactive users (no login in X days).
     */
    public function scopeInactive(Builder $query, int $days = 30): Builder
    {
        return $query->where(function ($q) use ($days) {
            $q->whereNull('last_login_at')
              ->orWhere('last_login_at', '<', now()->subDays($days));
        });
    }

    /**
     * Scope: Search by name or email.
     */
    public function scopeSearch(Builder $query, string $term): Builder
    {
        $term = '%' . $term . '%';
        return $query->where(function ($q) use ($term) {
            $q->where('name', 'like', $term)
              ->orWhere('email', 'like', $term)
              ->orWhere('phone', 'like', $term);
        });
    }

    /**
     * Scope: Order by popularity (activity count).
     */
    public function scopePopular(Builder $query): Builder
    {
        return $query->withCount('activities')
            ->orderByDesc('activities_count');
    }

    // =========================================================================
    // Role & Permission Methods
    // =========================================================================

    /**
     * Check if user has a specific role.
     */
    public function hasRole(string|array $roles): bool
    {
        $roles = (array) $roles;
        
        return Cache::remember(
            $this->getCacheKey('roles'),
            self::CACHE_TTL,
            fn () => $this->roles->pluck('name')->toArray()
        ) && !empty(array_intersect($roles, $this->getCachedRoles()));
    }

    /**
     * Check if user has a specific permission.
     */
    public function hasPermission(string $permission): bool
    {
        // Check direct permissions
        if (in_array($permission, $this->getCachedPermissions())) {
            return true;
        }

        // Check role-based permissions
        foreach ($this->getCachedRoles() as $role) {
            $rolePermissions = $this->getRolePermissions($role);
            if (in_array($permission, $rolePermissions)) {
                return true;
            }
        }

        return false;
    }

    /**
     * Check if user can perform an action.
     */
    public function can($ability, $arguments = []): bool
    {
        // Super admin can do anything
        if ($this->hasRole(self::ROLE_SUPER_ADMIN)) {
            return true;
        }

        return parent::can($ability, $arguments);
    }

    /**
     * Assign a role to the user.
     */
    public function assignRole(string $role, ?int $assignedBy = null, ?Carbon $expiresAt = null): void
    {
        $roleModel = Role::where('name', $role)->firstOrFail();
        
        $this->roles()->syncWithoutDetaching([
            $roleModel->id => [
                'assigned_by' => $assignedBy,
                'expires_at' => $expiresAt,
            ],
        ]);

        $this->clearCache();
    }

    /**
     * Remove a role from the user.
     */
    public function removeRole(string $role): void
    {
        $roleModel = Role::where('name', $role)->first();
        
        if ($roleModel) {
            $this->roles()->detach($roleModel->id);
            $this->clearCache();
        }
    }

    /**
     * Sync user roles.
     */
    public function syncRoles(array $roles): void
    {
        $roleIds = Role::whereIn('name', $roles)->pluck('id');
        $this->roles()->sync($roleIds);
        $this->clearCache();
    }

    /**
     * Get cached roles.
     */
    protected function getCachedRoles(): array
    {
        return Cache::remember(
            $this->getCacheKey('roles'),
            self::CACHE_TTL,
            fn () => $this->roles->pluck('name')->toArray()
        );
    }

    /**
     * Get cached permissions.
     */
    protected function getCachedPermissions(): array
    {
        return Cache::remember(
            $this->getCacheKey('permissions'),
            self::CACHE_TTL,
            fn () => $this->permissions->pluck('name')->toArray()
        );
    }

    /**
     * Get permissions for a role.
     */
    protected function getRolePermissions(string $role): array
    {
        return Cache::remember(
            "role:{$role}:permissions",
            self::CACHE_TTL,
            fn () => Role::where('name', $role)
                ->with('permissions')
                ->first()
                ?->permissions
                ->pluck('name')
                ->toArray() ?? []
        );
    }

    // =========================================================================
    // Two-Factor Authentication
    // =========================================================================

    /**
     * Check if 2FA is enabled.
     */
    public function hasTwoFactorEnabled(): bool
    {
        return !is_null($this->two_factor_confirmed_at);
    }

    /**
     * Enable two-factor authentication.
     */
    public function enableTwoFactor(string $secret, array $recoveryCodes): void
    {
        $this->forceFill([
            'two_factor_secret' => encrypt($secret),
            'two_factor_recovery_codes' => encrypt(json_encode($recoveryCodes)),
            'two_factor_confirmed_at' => now(),
        ])->save();
    }

    /**
     * Disable two-factor authentication.
     */
    public function disableTwoFactor(): void
    {
        $this->forceFill([
            'two_factor_secret' => null,
            'two_factor_recovery_codes' => null,
            'two_factor_confirmed_at' => null,
        ])->save();
    }

    /**
     * Get decrypted 2FA secret.
     */
    public function getTwoFactorSecret(): ?string
    {
        return $this->two_factor_secret
            ? decrypt($this->two_factor_secret)
            : null;
    }

    /**
     * Get recovery codes.
     */
    public function getRecoveryCodes(): array
    {
        if (!$this->two_factor_recovery_codes) {
            return [];
        }

        return json_decode(decrypt($this->two_factor_recovery_codes), true);
    }

    /**
     * Use a recovery code.
     */
    public function useRecoveryCode(string $code): bool
    {
        $codes = $this->getRecoveryCodes();
        $index = array_search($code, $codes);

        if ($index === false) {
            return false;
        }

        unset($codes[$index]);
        
        $this->forceFill([
            'two_factor_recovery_codes' => encrypt(json_encode(array_values($codes))),
        ])->save();

        return true;
    }

    // =========================================================================
    // Preferences & Settings
    // =========================================================================

    /**
     * Get a preference value.
     */
    public function getPreference(string $key, mixed $default = null): mixed
    {
        return data_get($this->preferences, $key, $default);
    }

    /**
     * Set a preference value.
     */
    public function setPreference(string $key, mixed $value): void
    {
        $preferences = $this->preferences;
        data_set($preferences, $key, $value);
        $this->preferences = $preferences;
        $this->save();
    }

    /**
     * Set multiple preferences.
     */
    public function setPreferences(array $preferences): void
    {
        $this->preferences = array_merge($this->preferences, $preferences);
        $this->save();
    }

    /**
     * Get metadata value.
     */
    public function getMeta(string $key, mixed $default = null): mixed
    {
        return data_get($this->metadata, $key, $default);
    }

    /**
     * Set metadata value.
     */
    public function setMeta(string $key, mixed $value): void
    {
        $metadata = $this->metadata;
        data_set($metadata, $key, $value);
        $this->metadata = $metadata;
        $this->save();
    }

    /**
     * Get default preferences.
     */
    public static function defaultPreferences(): array
    {
        return [
            'notifications' => [
                'email' => true,
                'push' => true,
                'sms' => false,
            ],
            'privacy' => [
                'profile_visible' => true,
                'show_email' => false,
                'show_phone' => false,
            ],
            'appearance' => [
                'theme' => 'system',
                'density' => 'comfortable',
            ],
        ];
    }

    // =========================================================================
    // Activity & Audit
    // =========================================================================

    /**
     * Log user activity.
     */
    public function logActivity(
        string $action,
        ?string $description = null,
        ?array $properties = null,
        ?string $subjectType = null,
        ?int $subjectId = null,
    ): void {
        Activity::create([
            'user_id' => $this->id,
            'action' => $action,
            'description' => $description,
            'properties' => $properties,
            'subject_type' => $subjectType,
            'subject_id' => $subjectId,
            'ip_address' => request()?->ip(),
            'user_agent' => request()?->userAgent(),
        ]);
    }

    /**
     * Record login.
     */
    public function recordLogin(?string $ip = null, ?string $userAgent = null): void
    {
        $this->forceFill([
            'last_login_at' => now(),
            'last_login_ip' => $ip ?? request()?->ip(),
        ])->save();

        $this->logActivity('login', 'User logged in');

        // Optionally track login history
        LoginHistory::create([
            'user_id' => $this->id,
            'ip_address' => $ip ?? request()?->ip(),
            'user_agent' => $userAgent ?? request()?->userAgent(),
            'location' => $this->getLocationFromIp($ip ?? request()?->ip()),
        ]);
    }

    /**
     * Get location from IP (placeholder for actual implementation).
     */
    protected function getLocationFromIp(?string $ip): ?string
    {
        // Implement with a geo-IP service
        return null;
    }

    // =========================================================================
    // Status Management
    // =========================================================================

    /**
     * Check if user is active.
     */
    public function isActive(): bool
    {
        return $this->status === self::STATUS_ACTIVE;
    }

    /**
     * Check if user is suspended.
     */
    public function isSuspended(): bool
    {
        return $this->status === self::STATUS_SUSPENDED;
    }

    /**
     * Check if user is banned.
     */
    public function isBanned(): bool
    {
        return $this->status === self::STATUS_BANNED;
    }

    /**
     * Activate the user.
     */
    public function activate(): void
    {
        $this->update(['status' => self::STATUS_ACTIVE]);
        $this->logActivity('status_change', 'Account activated');
    }

    /**
     * Suspend the user.
     */
    public function suspend(?string $reason = null): void
    {
        $this->update(['status' => self::STATUS_SUSPENDED]);
        $this->setMeta('suspension_reason', $reason);
        $this->setMeta('suspended_at', now()->toIso8601String());
        $this->logActivity('status_change', 'Account suspended', ['reason' => $reason]);
    }

    /**
     * Ban the user.
     */
    public function ban(?string $reason = null): void
    {
        $this->update(['status' => self::STATUS_BANNED]);
        $this->setMeta('ban_reason', $reason);
        $this->setMeta('banned_at', now()->toIso8601String());
        $this->logActivity('status_change', 'Account banned', ['reason' => $reason]);
        
        // Revoke all tokens
        $this->apiTokens()->delete();
    }

    // =========================================================================
    // Avatar Management
    // =========================================================================

    /**
     * Upload and set avatar.
     */
    public function uploadAvatar($file, string $disk = 'public'): string
    {
        // Delete old avatar
        $this->deleteAvatar();

        // Store new avatar
        $path = $file->store('avatars/' . $this->id, $disk);
        
        $this->update(['avatar' => $path]);

        return Storage::disk($disk)->url($path);
    }

    /**
     * Delete current avatar.
     */
    public function deleteAvatar(): void
    {
        if ($this->avatar && !Str::startsWith($this->avatar, ['http://', 'https://'])) {
            Storage::disk('public')->delete($this->avatar);
            $this->update(['avatar' => null]);
        }
    }

    // =========================================================================
    // Password Management
    // =========================================================================

    /**
     * Check if password matches.
     */
    public function checkPassword(string $password): bool
    {
        return Hash::check($password, $this->password);
    }

    /**
     * Update password.
     */
    public function updatePassword(string $password): void
    {
        $this->update(['password' => $password]); // Will be hashed via cast
        $this->logActivity('password_change', 'Password updated');
        
        // Optionally invalidate other sessions
        // $this->tokens()->delete();
    }

    /**
     * Check if password needs rehash.
     */
    public function passwordNeedsRehash(): bool
    {
        return Hash::needsRehash($this->password);
    }

    // =========================================================================
    // Notification Preferences
    // =========================================================================

    /**
     * Check if user wants email notifications.
     */
    public function wantsEmailNotifications(): bool
    {
        return $this->getPreference('notifications.email', true);
    }

    /**
     * Check if user wants push notifications.
     */
    public function wantsPushNotifications(): bool
    {
        return $this->getPreference('notifications.push', true);
    }

    /**
     * Get preferred notification channels.
     */
    public function preferredNotificationChannels(): array
    {
        $channels = ['database'];

        if ($this->wantsEmailNotifications()) {
            $channels[] = 'mail';
        }

        if ($this->wantsPushNotifications()) {
            $channels[] = 'broadcast';
        }

        return $channels;
    }

    // =========================================================================
    // Caching
    // =========================================================================

    /**
     * Get cache key for user data.
     */
    protected function getCacheKey(string $suffix): string
    {
        return "user:{$this->id}:{$suffix}";
    }

    /**
     * Clear user cache.
     */
    public function clearCache(): void
    {
        Cache::forget($this->getCacheKey('roles'));
        Cache::forget($this->getCacheKey('permissions'));
    }

    /**
     * Get cached user by ID.
     */
    public static function findCached(int $id): ?static
    {
        return Cache::remember(
            "user:{$id}:model",
            self::CACHE_TTL,
            fn () => static::find($id)
        );
    }

    // =========================================================================
    // Prunable
    // =========================================================================

    /**
     * Get the prunable model query.
     */
    public function prunable(): Builder
    {
        // Prune soft-deleted users older than 30 days
        return static::onlyTrashed()
            ->where('deleted_at', '<=', now()->subDays(30));
    }

    /**
     * Prepare the model for pruning.
     */
    protected function pruning(): void
    {
        // Clean up related data before permanent deletion
        $this->deleteAvatar();
        $this->apiTokens()->delete();
        $this->activities()->delete();
    }

    // =========================================================================
    // Utility Methods
    // =========================================================================

    /**
     * Get user's age if birthdate is stored.
     */
    public function getAge(): ?int
    {
        $birthdate = $this->getMeta('birthdate');
        
        if (!$birthdate) {
            return null;
        }

        return Carbon::parse($birthdate)->age;
    }

    /**
     * Get formatted created date.
     */
    public function memberSince(): string
    {
        return $this->created_at->diffForHumans();
    }

    /**
     * Check if user was recently created.
     */
    public function isNew(int $days = 7): bool
    {
        return $this->created_at->greaterThan(now()->subDays($days));
    }

    /**
     * Get public profile data.
     */
    public function getPublicProfile(): array
    {
        return [
            'id' => $this->id,
            'name' => $this->getPreference('privacy.show_name', true) ? $this->name : 'Anonymous',
            'avatar_url' => $this->avatar_url,
            'initials' => $this->initials,
            'member_since' => $this->memberSince(),
        ];
    }

    /**
     * Export user data (GDPR compliance).
     */
    public function exportData(): array
    {
        return [
            'profile' => $this->only([
                'id', 'name', 'email', 'phone', 'status',
                'locale', 'timezone', 'created_at',
            ]),
            'preferences' => $this->preferences,
            'metadata' => $this->metadata,
            'activities' => $this->activities()
                ->limit(1000)
                ->get()
                ->toArray(),
            'exported_at' => now()->toIso8601String(),
        ];
    }

    /**
     * Anonymize user data (GDPR right to be forgotten).
     */
    public function anonymize(): void
    {
        $anonymousId = Str::uuid()->toString();

        $this->forceFill([
            'name' => 'Deleted User',
            'email' => "{$anonymousId}@deleted.local",
            'phone' => null,
            'avatar' => null,
            'password' => Hash::make(Str::random(32)),
            'preferences' => [],
            'metadata' => ['anonymized_at' => now()->toIso8601String()],
            'remember_token' => null,
        ])->save();

        $this->deleteAvatar();
        $this->apiTokens()->delete();
        $this->socialAccounts()->delete();
        
        $this->logActivity('anonymize', 'User data anonymized');
    }

    /**
     * Convert to array with additional computed fields.
     */
    public function toArray(): array
    {
        return array_merge(parent::toArray(), [
            'is_verified' => !is_null($this->email_verified_at),
            'has_2fa' => $this->hasTwoFactorEnabled(),
        ]);
    }
}
