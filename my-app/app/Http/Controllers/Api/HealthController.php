<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

final class HealthController extends ApiController
{
    public function __invoke(Request $request): JsonResponse
    {
        return $this->ok($request, [
            'ok' => true,
            'app' => (string) config('app.name', 'app'),
            'env' => (string) config('app.env', 'unknown'),
        ]);
    }
}
