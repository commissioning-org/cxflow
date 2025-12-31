<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * Social Account model for OAuth authentication.
 *
 * @property int $id
 * @property int $user_id
 * @property string $provider
 * @property string $provider_id
 * @property string|null $token
 * @property string|null $refresh_token
 * @property \Illuminate\Support\Carbon|null $token_expires_at
 * @property string|null $avatar
 * @property array|null $metadata
 * @property \Illuminate\Support\Carbon $created_at
 * @property \Illuminate\Support\Carbon $updated_at
 */
class SocialAccount extends Model
{
    use HasFactory;

    protected $fillable = [
        'user_id',
        'provider',
        'provider_id',
        'token',
        'refresh_token',
        'token_expires_at',
        'avatar',
        'metadata',
    ];

    protected $hidden = [
        'token',
        'refresh_token',
    ];

    protected $casts = [
        'token_expires_at' => 'datetime',
        'metadata' => 'array',
    ];

    /**
     * Supported providers.
     */
    public const PROVIDERS = [
        'google',
        'github',
        'facebook',
        'twitter',
        'linkedin',
        'apple',
        'microsoft',
    ];

    /**
     * The user who owns this social account.
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Check if token needs refresh.
     */
    public function tokenNeedsRefresh(): bool
    {
        if (!$this->token_expires_at) {
            return false;
        }

        // Refresh if expires within 5 minutes
        return $this->token_expires_at->subMinutes(5)->isPast();
    }

    /**
     * Update tokens from OAuth response.
     */
    public function updateTokens(
        string $token,
        ?string $refreshToken = null,
        ?int $expiresIn = null
    ): void {
        $this->update([
            'token' => encrypt($token),
            'refresh_token' => $refreshToken ? encrypt($refreshToken) : $this->refresh_token,
            'token_expires_at' => $expiresIn ? now()->addSeconds($expiresIn) : null,
        ]);
    }

    /**
     * Get decrypted token.
     */
    public function getDecryptedToken(): ?string
    {
        return $this->token ? decrypt($this->token) : null;
    }

    /**
     * Get decrypted refresh token.
     */
    public function getDecryptedRefreshToken(): ?string
    {
        return $this->refresh_token ? decrypt($this->refresh_token) : null;
    }

    /**
     * Find or create from OAuth user.
     */
    public static function findOrCreateFromOAuth(
        string $provider,
        object $oauthUser,
        ?User $user = null
    ): static {
        $account = static::where('provider', $provider)
            ->where('provider_id', $oauthUser->getId())
            ->first();

        if ($account) {
            $account->updateTokens(
                $oauthUser->token,
                $oauthUser->refreshToken ?? null,
                $oauthUser->expiresIn ?? null
            );
            return $account;
        }

        // Create new user if not provided
        if (!$user) {
            $user = User::create([
                'name' => $oauthUser->getName() ?? $oauthUser->getNickname(),
                'email' => $oauthUser->getEmail(),
                'password' => bcrypt(\Illuminate\Support\Str::random(32)),
                'email_verified_at' => now(),
                'avatar' => $oauthUser->getAvatar(),
            ]);
        }

        return static::create([
            'user_id' => $user->id,
            'provider' => $provider,
            'provider_id' => $oauthUser->getId(),
            'token' => encrypt($oauthUser->token),
            'refresh_token' => $oauthUser->refreshToken ? encrypt($oauthUser->refreshToken) : null,
            'token_expires_at' => $oauthUser->expiresIn ? now()->addSeconds($oauthUser->expiresIn) : null,
            'avatar' => $oauthUser->getAvatar(),
            'metadata' => [
                'nickname' => $oauthUser->getNickname(),
                'email' => $oauthUser->getEmail(),
            ],
        ]);
    }
}
