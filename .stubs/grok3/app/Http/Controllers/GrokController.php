<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Services\Llm\GithubModelsClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

final class GrokController extends Controller
{
    public function __construct(private readonly GithubModelsClient $client)
    {
    }

    public function chat(Request $request): JsonResponse
    {
        $data = $request->validate([
            'prompt' => ['required', 'string', 'max:8000'],
        ]);

        $text = $this->client->chatText([
            ['role' => 'system', 'content' => 'You are Grok-3. Be concise and accurate.'],
            ['role' => 'user', 'content' => $data['prompt']],
        ]);

        return response()->json([
            'model' => config('llm.github_models.model', 'grok-3'),
            'reply' => $text,
        ]);
    }
}
