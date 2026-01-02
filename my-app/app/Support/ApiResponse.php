<?php

declare(strict_types=1);

namespace App\Support;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

final class ApiResponse
{
    /**
     * @param array<string, mixed> $data
     * @param array<string, mixed> $meta
     */
    public static function ok(Request $request, array $data = [], int $status = 200, array $meta = []): JsonResponse
    {
        return response()->json([
            'status' => 'success',
            'data' => (object) $data,
            'meta' => array_merge(self::defaultMeta($request), $meta),
        ], $status);
    }

    /**
     * @param array<string, mixed> $data
     * @param array<string, mixed> $meta
     */
    public static function created(Request $request, array $data = [], array $meta = []): JsonResponse
    {
        return self::ok($request, $data, 201, $meta);
    }

    /**
     * @param array<string, mixed> $meta
     * @param array<string, mixed> $errors
     */
    public static function error(
        Request $request,
        string $message,
        int $status,
        array $errors = [],
        array $meta = [],
        ?string $code = null,
    ): JsonResponse {
        $payload = [
            'status' => 'error',
            'message' => $message,
            'meta' => array_merge(self::defaultMeta($request), $meta),
        ];

        if ($code !== null) {
            $payload['code'] = $code;
        }

        if ($errors !== []) {
            $payload['errors'] = $errors;
        }

        return response()->json($payload, $status);
    }

    /**
     * @return array{request_id: string|null, timestamp: string, version: string}
     */
    private static function defaultMeta(Request $request): array
    {
        return [
            'request_id' => $request->header('X-Request-Id'),
            'timestamp' => now()->toIso8601String(),
            'version' => (string) config('app.version', '1.0'),
        ];
    }
}
