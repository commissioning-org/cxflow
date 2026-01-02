<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Support\ApiResponse;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

abstract class ApiController extends Controller
{
    /**
     * @param array<string, mixed> $data
     * @param array<string, mixed> $meta
     */
    protected function ok(Request $request, array $data = [], int $status = 200, array $meta = []): JsonResponse
    {
        return ApiResponse::ok($request, $data, $status, $meta);
    }

    /**
     * @param array<string, mixed> $data
     * @param array<string, mixed> $meta
     */
    protected function created(Request $request, array $data = [], array $meta = []): JsonResponse
    {
        return ApiResponse::created($request, $data, $meta);
    }

    /**
     * @param array<string, mixed> $errors
     * @param array<string, mixed> $meta
     */
    protected function error(Request $request, string $message, int $status, array $errors = [], array $meta = [], ?string $code = null): JsonResponse
    {
        return ApiResponse::error($request, $message, $status, $errors, $meta, $code);
    }
}
