<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Symfony\Component\HttpFoundation\Response;

final class RequestContextMiddleware
{
    /**
     * @param Closure(Request): Response $next
     */
    public function handle(Request $request, Closure $next): Response
    {
        $requestId = $request->header('X-Request-Id');

        Log::withContext([
            'request_id' => $requestId,
            'ip' => $request->ip(),
            'method' => $request->method(),
            'path' => '/' . ltrim($request->path(), '/'),
        ]);

        return $next($request);
    }
}
