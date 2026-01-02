<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Services\Assistant\Contracts\Assistant;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class AssistantTest extends TestCase
{
    use RefreshDatabase;

    public function test_assistant_text_endpoint_uses_service_and_returns_text(): void
    {
        $this->mock(Assistant::class, function ($mock): void {
            $mock->shouldReceive('text')
                ->once()
                ->andReturn('hello from assistant');
        });

        $resp = $this->postJson('/api/assistant/text', [
            'prompt' => 'Say hello',
            'options' => ['temperature' => 0.0],
        ]);

        $resp->assertOk();
        $resp->assertJsonPath('data.text', 'hello from assistant');
    }

    public function test_assistant_json_endpoint_uses_service_and_returns_json(): void
    {
        $this->mock(Assistant::class, function ($mock): void {
            $mock->shouldReceive('json')
                ->once()
                ->andReturn(['ok' => true]);
        });

        $resp = $this->postJson('/api/assistant/json', [
            'prompt' => 'Return ok',
            'options' => ['temperature' => 0.0],
        ]);

        $resp->assertOk();
        $resp->assertJsonPath('data.json.ok', true);
    }
}
