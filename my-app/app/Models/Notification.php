<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Carbon;

/**
 * Custom Notification model extending Laravel's default.
 *
 * @property string $id
 * @property string $type
 * @property int $user_id
 * @property array $data
 * @property string|null $category
 * @property string $priority
 * @property Carbon|null $read_at
 * @property Carbon|null $actioned_at
 * @property Carbon $created_at
 * @property Carbon $updated_at
 */
class Notification extends Model
{
    /** Priority levels */
    public const PRIORITY_LOW = 'low';
    public const PRIORITY_NORMAL = 'normal';
    public const PRIORITY_HIGH = 'high';
    public const PRIORITY_URGENT = 'urgent';

    /** Categories */
    public const CATEGORY_SYSTEM = 'system';
    public const CATEGORY_ACCOUNT = 'account';
    public const CATEGORY_SECURITY = 'security';
    public const CATEGORY_MARKETING = 'marketing';
    public const CATEGORY_SOCIAL = 'social';

    protected $keyType = 'string';
    public $incrementing = false;

    protected $fillable = [
        'id',
        'type',
        'user_id',
        'data',
        'category',
        'priority',
        'read_at',
        'actioned_at',
    ];

    protected $casts = [
        'data' => 'array',
        'read_at' => 'datetime',
        'actioned_at' => 'datetime',
    ];

    protected $attributes = [
        'priority' => self::PRIORITY_NORMAL,
        'category' => self::CATEGORY_SYSTEM,
    ];

    /**
     * The user who received the notification.
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Check if notification is read.
     */
    public function isRead(): bool
    {
        return !is_null($this->read_at);
    }

    /**
     * Check if notification has been actioned.
     */
    public function isActioned(): bool
    {
        return !is_null($this->actioned_at);
    }

    /**
     * Mark notification as read.
     */
    public function markAsRead(): void
    {
        if (is_null($this->read_at)) {
            $this->update(['read_at' => now()]);
        }
    }

    /**
     * Mark notification as unread.
     */
    public function markAsUnread(): void
    {
        $this->update(['read_at' => null]);
    }

    /**
     * Mark notification as actioned.
     */
    public function markAsActioned(): void
    {
        $this->update([
            'read_at' => $this->read_at ?? now(),
            'actioned_at' => now(),
        ]);
    }

    /**
     * Get notification title from data.
     */
    public function getTitle(): string
    {
        return $this->data['title'] ?? class_basename($this->type);
    }

    /**
     * Get notification message from data.
     */
    public function getMessage(): string
    {
        return $this->data['message'] ?? $this->data['body'] ?? '';
    }

    /**
     * Get action URL from data.
     */
    public function getActionUrl(): ?string
    {
        return $this->data['action_url'] ?? $this->data['url'] ?? null;
    }

    /**
     * Scope: Unread notifications.
     */
    public function scopeUnread(Builder $query): Builder
    {
        return $query->whereNull('read_at');
    }

    /**
     * Scope: Read notifications.
     */
    public function scopeRead(Builder $query): Builder
    {
        return $query->whereNotNull('read_at');
    }

    /**
     * Scope: By category.
     */
    public function scopeCategory(Builder $query, string $category): Builder
    {
        return $query->where('category', $category);
    }

    /**
     * Scope: By priority.
     */
    public function scopePriority(Builder $query, string $priority): Builder
    {
        return $query->where('priority', $priority);
    }

    /**
     * Scope: High priority (high and urgent).
     */
    public function scopeHighPriority(Builder $query): Builder
    {
        return $query->whereIn('priority', [self::PRIORITY_HIGH, self::PRIORITY_URGENT]);
    }

    /**
     * Scope: Recent notifications.
     */
    public function scopeRecent(Builder $query, int $days = 30): Builder
    {
        return $query->where('created_at', '>=', now()->subDays($days));
    }

    /**
     * Mark all user notifications as read.
     */
    public static function markAllAsReadForUser(User $user): int
    {
        return static::where('user_id', $user->id)
            ->whereNull('read_at')
            ->update(['read_at' => now()]);
    }

    /**
     * Get unread count for user.
     */
    public static function unreadCountForUser(User $user): int
    {
        return static::where('user_id', $user->id)
            ->whereNull('read_at')
            ->count();
    }

    /**
     * Delete old notifications.
     */
    public static function deleteOld(int $days = 90): int
    {
        return static::where('created_at', '<', now()->subDays($days))
            ->whereNotNull('read_at')
            ->delete();
    }
}
