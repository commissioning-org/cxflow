<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;
use Illuminate\Support\Str;

final class UsersTest extends TestCase
{
    use RefreshDatabase;

    public function test_users_index_returns_paginated_users(): void
    {
        $token = $this->issueTokenWithAbilities(['api.access']);
        User::factory()->count(3)->create();

        $resp = $this->withHeader('Authorization', 'Bearer '.$token)->getJson('/api/users');

        $resp->assertOk();
        $resp->assertJsonPath('status', 'success');

        // UserCollection shape
        $resp->assertJsonStructure([
            'data' => [
                '*' => ['id', 'name', 'avatar_url', 'status', 'created_at', 'links'],
            ],
            'meta' => ['total', 'per_page', 'current_page', 'last_page', 'from', 'to'],
            'links' => ['first', 'last', 'prev', 'next'],
            'status',
            'version',
        ]);
    }

    public function test_users_show_returns_single_user_resource(): void
    {
        $token = $this->issueTokenWithAbilities(['api.access']);
        $user = User::factory()->create();

        $resp = $this->withHeader('Authorization', 'Bearer '.$token)->getJson('/api/users/' . $user->id);

        $resp->assertOk();
        $resp->assertJsonPath('data.id', $user->id);
        $resp->assertJsonStructure([
            'data' => ['id', 'name', 'links'],
            'meta' => ['version'],
        ]);
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
