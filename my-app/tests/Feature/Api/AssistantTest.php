<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Services\Assistant\Contracts\Assistant;
use Illuminate\Foundation\Testing\RefreshDatabase;
use App\Models\User;
use Illuminate\Support\Str;
use Tests\TestCase;

final class AssistantTest extends TestCase
{
    use RefreshDatabase;

    public function test_assistant_text_endpoint_uses_service_and_returns_text(): void
    {
        $token = $this->issueTokenWithAbilities(['api.access', 'assistant.use']);

        $this->mock(Assistant::class, function ($mock): void {
            $mock->shouldReceive('text')
                ->once()
                ->andReturn('hello from assistant');
        });

        $resp = $this->withHeader('Authorization', 'Bearer '.$token)->postJson('/api/assistant/text', [
            'prompt' => 'Say hello',
            'options' => ['temperature' => 0.0],
        ]);

        $resp->assertOk();
        $resp->assertJsonPath('data.text', 'hello from assistant');
    }

    public function test_assistant_json_endpoint_uses_service_and_returns_json(): void
    {
        $token = $this->issueTokenWithAbilities(['api.access', 'assistant.use']);

        $this->mock(Assistant::class, function ($mock): void {
            $mock->shouldReceive('json')
                ->once()
                ->andReturn(['ok' => true]);
        });

        $resp = $this->withHeader('Authorization', 'Bearer '.$token)->postJson('/api/assistant/json', [
            'prompt' => 'Return ok',
            'options' => ['temperature' => 0.0],
        ]);

        $resp->assertOk();
        $resp->assertJsonPath('data.json.ok', true);
    }

    private function issueTokenWithAbilities(array $abilities): string
    {
        $password = 'password-'.Str::random(10);
        $user = User::factory()->create([
            'status' => User::STATUS_ACTIVE,
            'password' => bcrypt($password),
        ]);

        $response = $this->postJson('/api/auth/login', [
            'email' => $user->email,
            'password' => $password,
            'token_name' => 'test',
            'abilities' => $abilities,
            'expires_in_days' => 30,
        ]);

        $response->assertCreated();

        return (string) $response->json('data.token.plain');
    }
}
