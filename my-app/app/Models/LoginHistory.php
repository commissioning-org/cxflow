<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Builder;

/**
 * Login History model for security auditing.
 *
 * @property int $id
 * @property int $user_id
 * @property string|null $ip_address
 * @property string|null $user_agent
 * @property string|null $location
 * @property bool $successful
 * @property string|null $failure_reason
 * @property \Illuminate\Support\Carbon $created_at
 * @property \Illuminate\Support\Carbon $updated_at
 */
class LoginHistory extends Model
{
    use HasFactory;

    protected $table = 'login_history';

    protected $fillable = [
        'user_id',
        'ip_address',
        'user_agent',
        'location',
        'successful',
        'failure_reason',
    ];

    protected $casts = [
        'successful' => 'boolean',
    ];

    /**
     * The user who made the login attempt.
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Get parsed user agent info.
     */
    public function getParsedUserAgent(): array
    {
        $agent = $this->user_agent ?? '';

        return [
            'browser' => $this->extractBrowser($agent),
            'platform' => $this->extractPlatform($agent),
            'device' => $this->extractDevice($agent),
        ];
    }

    /**
     * Extract browser from user agent.
     */
    protected function extractBrowser(string $agent): string
    {
        $browsers = [
            'Edge' => '/Edge\/[\d.]+/',
            'Chrome' => '/Chrome\/[\d.]+/',
            'Firefox' => '/Firefox\/[\d.]+/',
            'Safari' => '/Safari\/[\d.]+/',
            'Opera' => '/Opera\/[\d.]+/',
            'IE' => '/MSIE [\d.]+/',
        ];

        foreach ($browsers as $name => $pattern) {
            if (preg_match($pattern, $agent)) {
                return $name;
            }
        }

        return 'Unknown';
    }

    /**
     * Extract platform from user agent.
     */
    protected function extractPlatform(string $agent): string
    {
        $platforms = [
            'Windows' => '/Windows/',
            'macOS' => '/Macintosh/',
            'Linux' => '/Linux/',
            'iOS' => '/iPhone|iPad/',
            'Android' => '/Android/',
        ];

        foreach ($platforms as $name => $pattern) {
            if (preg_match($pattern, $agent)) {
                return $name;
            }
        }

        return 'Unknown';
    }

    /**
     * Extract device type from user agent.
     */
    protected function extractDevice(string $agent): string
    {
        if (preg_match('/Mobile|Android|iPhone/', $agent)) {
            return 'Mobile';
        }
        if (preg_match('/Tablet|iPad/', $agent)) {
            return 'Tablet';
        }
        return 'Desktop';
    }

    /**
     * Scope: Successful logins.
     */
    public function scopeSuccessful(Builder $query): Builder
    {
        return $query->where('successful', true);
    }

    /**
     * Scope: Failed logins.
     */
    public function scopeFailed(Builder $query): Builder
    {
        return $query->where('successful', false);
    }

    /**
     * Scope: Recent logins.
     */
    public function scopeRecent(Builder $query, int $days = 30): Builder
    {
        return $query->where('created_at', '>=', now()->subDays($days));
    }

    /**
     * Scope: From specific IP.
     */
    public function scopeFromIp(Builder $query, string $ip): Builder
    {
        return $query->where('ip_address', $ip);
    }

    /**
     * Check for suspicious activity.
     */
    public static function hasSuspiciousActivity(User $user, int $threshold = 5): bool
    {
        // Check for multiple failed logins in last hour
        $failedCount = static::where('user_id', $user->id)
            ->failed()
            ->where('created_at', '>=', now()->subHour())
            ->count();

        return $failedCount >= $threshold;
    }

    /**
     * Get unique login locations for user.
     */
    public static function getUniqueLocations(User $user, int $days = 30): array
    {
        return static::where('user_id', $user->id)
            ->successful()
            ->recent($days)
            ->whereNotNull('location')
            ->distinct()
            ->pluck('location')
            ->toArray();
    }

    /**
     * Record a login attempt.
     */
    public static function record(
        ?User $user,
        bool $successful = true,
        ?string $failureReason = null
    ): static {
        return static::create([
            'user_id' => $user?->id,
            'ip_address' => request()?->ip(),
            'user_agent' => request()?->userAgent(),
            'location' => null, // Implement with geo-IP service
            'successful' => $successful,
            'failure_reason' => $failureReason,
        ]);
    }
}
