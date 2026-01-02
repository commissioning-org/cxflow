<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use App\Models\ApiToken;
use App\Support\ApiResponse;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

final class RequireTokenAbilityMiddleware
{
    /**
     * Require that the authenticated API token has the given ability.
     *
     * Usage:
     *   ->middleware('ability:assistant.use')
     *
     * @param Closure(Request): Response $next
     */
    public function handle(Request $request, Closure $next, string $ability): Response
    {
        /** @var ApiToken|null $token */
        $token = $request->attributes->get('api_token');

        // If the request is authenticated through other means (e.g. session), allow.
        if ($token === null) {
            return $next($request);
        }

        if (!$token->hasAbility($ability)) {
            return ApiResponse::error(
                request: $request,
                message: 'Forbidden.',
                status: 403,
                code: 'forbidden',
                errors: ['ability' => [$ability]],
            );
        }

        return $next($request);
    }
}
