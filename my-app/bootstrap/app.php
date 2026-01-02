<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Auth\Access\AuthorizationException;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Http\Request;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;
use App\Support\ApiResponse;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->alias([
            'auth.token' => App\Http\Middleware\ApiTokenAuthMiddleware::class,
            'ability' => App\Http\Middleware\RequireTokenAbilityMiddleware::class,
        ]);

        $middleware->api(append: [
            App\Http\Middleware\RequestIdMiddleware::class,
            App\Http\Middleware\RequestContextMiddleware::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->render(function (\Throwable $e, Request $request) {
            // Only shape JSON for API-style requests.
            if (!$request->expectsJson() && !$request->is('api/*')) {
                return null;
            }

            if ($e instanceof ValidationException) {
                return ApiResponse::error(
                    request: $request,
                    message: 'Validation failed.',
                    status: 422,
                    errors: $e->errors(),
                    code: 'validation_error',
                );
            }

            if ($e instanceof AuthenticationException) {
                return ApiResponse::error(
                    request: $request,
                    message: 'Unauthenticated.',
                    status: 401,
                    code: 'unauthenticated',
                );
            }

            if ($e instanceof AuthorizationException) {
                return ApiResponse::error(
                    request: $request,
                    message: 'Forbidden.',
                    status: 403,
                    code: 'forbidden',
                );
            }

            if ($e instanceof ModelNotFoundException) {
                return ApiResponse::error(
                    request: $request,
                    message: 'Not found.',
                    status: 404,
                    code: 'not_found',
                );
            }

            // Preserve HTTP exceptions (404/403/etc) while hiding internal details.
            if ($e instanceof HttpExceptionInterface) {
                $status = $e->getStatusCode();
                $message = $status === 404 ? 'Not found.' : ($status === 403 ? 'Forbidden.' : 'Request failed.');

                return ApiResponse::error(
                    request: $request,
                    message: $message,
                    status: $status,
                    code: 'http_error',
                );
            }

            $status = 500;
            $message = 'Server error.';
            $meta = [];

            if ((bool) config('app.debug', false)) {
                $meta = [
                    'exception' => get_class($e),
                    'detail' => $e->getMessage(),
                ];
            }

            return ApiResponse::error(
                request: $request,
                message: $message,
                status: $status,
                meta: $meta,
                code: 'server_error',
            );
        });
    })->create();
