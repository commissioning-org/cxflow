<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class UsersTest extends TestCase
{
    use RefreshDatabase;

    public function test_users_index_returns_paginated_users(): void
    {
        User::factory()->count(3)->create();

        $resp = $this->getJson('/api/users');

        $resp->assertOk();
        $resp->assertJsonPath('status', 'success');

        // UserCollection shape
        $resp->assertJsonStructure([
            'data' => [
                '*' => ['id', 'name', 'email', 'avatar_url', 'status', 'created_at', 'links'],
            ],
            'meta' => ['total', 'per_page', 'current_page', 'last_page', 'from', 'to'],
            'links' => ['first', 'last', 'prev', 'next'],
            'status',
            'version',
        ]);
    }

    public function test_users_show_returns_single_user_resource(): void
    {
        $user = User::factory()->create();

        $resp = $this->getJson('/api/users/' . $user->id);

        $resp->assertOk();
        $resp->assertJsonPath('data.id', $user->id);
        $resp->assertJsonStructure([
            'data' => ['id', 'name', 'email', 'links'],
            'meta' => ['version'],
        ]);
    }
}
