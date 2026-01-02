<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Http\Requests\Api\CreateApiTokenRequest;
use App\Http\Resources\ApiTokenResource;
use App\Models\Activity;
use App\Models\ApiToken;
use App\Models\User;
use App\Services\Auth\TokenAbilityResolver;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

final class ApiTokenController extends ApiController
{
    public function index(Request $request): JsonResponse
    {
        /** @var User $user */
        $user = $request->user();

        $tokens = $user->apiTokens()->orderByDesc('created_at')->get();

        return $this->ok($request, [
            'tokens' => ApiTokenResource::collection($tokens)->resolve($request),
        ]);
    }

    public function store(CreateApiTokenRequest $request, TokenAbilityResolver $resolver): JsonResponse
    {
        /** @var User $user */
        $user = $request->user();

        $expiresAt = null;
        if (($days = $request->expiresInDays()) !== null) {
            $expiresAt = now()->addDays($days);
        }

        $requested = $request->abilities();
        $abilities = $resolver->restrict($user, $requested);

        $tokenData = ApiToken::generate(
            user: $user,
            name: $request->tokenName(),
            abilities: $abilities,
            expiresAt: $expiresAt,
        );

        /** @var ApiToken $token */
        $token = $tokenData['token'];
        $plain = (string) $tokenData['plain_token'];

        Activity::log(
            action: 'api_tokens.create',
            description: 'API token created',
            properties: ['token_id' => $token->id, 'name' => $token->name],
            subject: $token,
            user: $user,
        );

        return $this->created($request, [
            'token' => array_merge(
                (new ApiTokenResource($token))->resolve($request),
                ['plain' => $plain],
            ),
        ]);
    }

    public function destroy(Request $request, ApiToken $token): JsonResponse
    {
        /** @var User $user */
        $user = $request->user();

        // Only allow revoking your own tokens.
        if ((int) $token->user_id !== (int) $user->id) {
            return $this->error(
                request: $request,
                message: 'Not found.',
                status: 404,
                code: 'not_found',
            );
        }

        Activity::log(
            action: 'api_tokens.revoke',
            description: 'API token revoked',
            properties: ['token_id' => $token->id, 'name' => $token->name],
            subject: $token,
            user: $user,
        );

        $token->delete();

        return $this->ok($request, ['ok' => true]);
    }
}
