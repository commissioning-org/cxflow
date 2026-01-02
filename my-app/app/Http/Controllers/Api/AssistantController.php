<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Http\Requests\Api\AssistantJsonRequest;
use App\Http\Requests\Api\AssistantTextRequest;
use App\Services\Assistant\Contracts\Assistant;
use Illuminate\Http\JsonResponse;

final class AssistantController extends ApiController
{
    public function __construct(private readonly Assistant $assistant)
    {
    }

    public function text(AssistantTextRequest $request): JsonResponse
    {
        $text = $this->assistant->text(
            prompt: (string) $request->validated('prompt'),
            options: $request->options(),
        );

        return $this->ok($request, ['text' => $text]);
    }

    public function json(AssistantJsonRequest $request): JsonResponse
    {
        $json = $this->assistant->json(
            prompt: (string) $request->validated('prompt'),
            options: $request->options(),
        );

        return $this->ok($request, ['json' => $json]);
    }
}
