<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use App\Models\ApiToken;
use App\Support\ApiResponse;
use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Symfony\Component\HttpFoundation\Response;

final class ApiTokenAuthMiddleware
{
    /**
     * Authenticate API requests via Authorization: Bearer <token>.
     *
     * On success:
     * - sets the authenticated user (so $request->user() works)
     * - attaches the ApiToken model at $request->attributes->get('api_token')
     *
     * @param Closure(Request): Response $next
     */
    public function handle(Request $request, Closure $next): Response
    {
        // Already authenticated (e.g. session auth in dev)
        if ($request->user() !== null) {
            return $next($request);
        }

        $plainToken = $this->extractBearerToken($request);
        if ($plainToken === null) {
            return ApiResponse::error(
                request: $request,
                message: 'Unauthenticated.',
                status: 401,
                code: 'unauthenticated',
            );
        }

        $token = ApiToken::query()
            ->valid()
            ->where('token', hash('sha256', $plainToken))
            ->with('user')
            ->first();

        if ($token === null || $token->user === null) {
            return ApiResponse::error(
                request: $request,
                message: 'Unauthenticated.',
                status: 401,
                code: 'unauthenticated',
            );
        }

        // Soft-block suspended/banned users.
        if (in_array($token->user->status, ['suspended', 'banned'], true)) {
            return ApiResponse::error(
                request: $request,
                message: 'Forbidden.',
                status: 403,
                code: 'forbidden',
            );
        }

        // Attach to request and auth facade.
        $request->attributes->set('api_token', $token);
        Auth::setUser($token->user);

        // Best-effort last_used_at update (avoid a write on every request).
        try {
            $last = $token->last_used_at;
            if ($last === null || $last->lt(now()->subMinute())) {
                $token->forceFill(['last_used_at' => now()])->save();
            }
        } catch (\Throwable) {
            // ignore
        }

        return $next($request);
    }

    private function extractBearerToken(Request $request): ?string
    {
        $header = $request->header('Authorization');
        if (!is_string($header) || trim($header) === '') {
            return null;
        }

        // Accept "Bearer <token>" (standard)
        if (stripos($header, 'Bearer ') === 0) {
            $token = trim(substr($header, 7));
            return $token !== '' ? $token : null;
        }

        // Accept "Token <token>" (some clients)
        if (stripos($header, 'Token ') === 0) {
            $token = trim(substr($header, 6));
            return $token !== '' ? $token : null;
        }

        return null;
    }
}
