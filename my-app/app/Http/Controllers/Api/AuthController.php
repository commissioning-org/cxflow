<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Http\Requests\Api\LoginRequest;
use App\Http\Resources\UserResource;
use App\Models\Activity;
use App\Models\ApiToken;
use App\Models\User;
use App\Services\Auth\TokenAbilityResolver;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;

final class AuthController extends ApiController
{
    public function login(LoginRequest $request): JsonResponse
    {
        $email = (string) $request->validated('email');
        $password = (string) $request->validated('password');

        $user = User::query()->where('email', $email)->first();

        // Avoid user enumeration: same response whether user exists or not.
        if ($user === null || !Hash::check($password, (string) $user->password)) {
            return $this->error(
                request: $request,
                message: 'Invalid credentials.',
                status: 401,
                code: 'invalid_credentials',
            );
        }

        if ($user->status !== User::STATUS_ACTIVE) {
            return $this->error(
                request: $request,
                message: 'Forbidden.',
                status: 403,
                code: 'forbidden',
            );
        }

        // Only allow API login if the user is permitted to access the API at all.
        if (!$user->hasPermission('api.access') && !$user->hasRole(User::ROLE_SUPER_ADMIN)) {
            return $this->error(
                request: $request,
                message: 'Forbidden.',
                status: 403,
                code: 'forbidden',
            );
        }

        $expiresAt = null;
        if (($days = $request->expiresInDays()) !== null) {
            $expiresAt = now()->addDays($days);
        }

        $abilities = app(TokenAbilityResolver::class)->restrict(
            user: $user,
            requested: $request->abilities(),
        );

        $tokenData = ApiToken::generate(
            user: $user,
            name: $request->tokenName(),
            abilities: $abilities,
            expiresAt: $expiresAt,
        );

        /** @var ApiToken $token */
        $token = $tokenData['token'];
        $plain = (string) $tokenData['plain_token'];

        // Track login.
        $user->forceFill([
            'last_login_at' => now(),
            'last_login_ip' => $request->ip(),
        ])->save();

        Activity::log(
            action: 'auth.login',
            description: 'API login via token issuance',
            properties: ['token_id' => $token->id, 'name' => $token->name],
            subject: $token,
            user: $user,
        );

        return $this->created($request, [
            'token' => [
                'id' => $token->id,
                'name' => $token->name,
                'abilities' => $token->abilities ?? [],
                'expires_at' => $token->expires_at?->toIso8601String(),
                'plain' => $plain,
            ],
            'user' => (new UserResource($user))->resolve($request),
        ]);
    }

    public function me(Request $request): UserResource
    {
        /** @var User $user */
        $user = $request->user();

        $user->loadMissing('roles');

        return new UserResource($user);
    }

    public function logout(Request $request): JsonResponse
    {
        /** @var ApiToken|null $token */
        $token = $request->attributes->get('api_token');

        if ($token !== null) {
            Activity::log(
                action: 'auth.logout',
                description: 'API logout (token revoked)',
                properties: ['token_id' => $token->id, 'name' => $token->name],
                subject: $token,
                user: $request->user(),
            );

            $token->delete();
        }

        return $this->ok($request, ['ok' => true]);
    }

}
