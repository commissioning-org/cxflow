<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

final class AuthTest extends TestCase
{
    use RefreshDatabase;

    public function test_login_issues_token_and_me_returns_user(): void
    {
        $password = 'password-'.Str::random(10);
        $user = User::factory()->create([
            'status' => User::STATUS_ACTIVE,
            'password' => bcrypt($password),
        ]);

        $login = $this->postJson('/api/auth/login', [
            'email' => $user->email,
            'password' => $password,
            'token_name' => 'test',
            'abilities' => ['api.access'],
        ]);

        $login->assertCreated();
        $token = (string) $login->json('data.token.plain');
        $this->assertNotSame('', $token);

        $me = $this->withHeader('Authorization', 'Bearer '.$token)->getJson('/api/auth/me');
        $me->assertOk();
        $me->assertJsonPath('data.id', $user->id);
    }

    public function test_logout_revokes_token(): void
    {
        $password = 'password-'.Str::random(10);
        $user = User::factory()->create([
            'status' => User::STATUS_ACTIVE,
            'password' => bcrypt($password),
        ]);

        $login = $this->postJson('/api/auth/login', [
            'email' => $user->email,
            'password' => $password,
            'token_name' => 'test',
            'abilities' => ['api.access'],
        ]);

        $token = (string) $login->json('data.token.plain');

        $logout = $this->withHeader('Authorization', 'Bearer '.$token)->postJson('/api/auth/logout');
        $logout->assertOk();
        $logout->assertJsonPath('data.ok', true);

        $me = $this->withHeader('Authorization', 'Bearer '.$token)->getJson('/api/auth/me');
        $me->assertStatus(401);
        $me->assertJsonPath('status', 'error');
        $me->assertJsonPath('code', 'unauthenticated');
    }

    public function test_login_rejects_invalid_credentials(): void
    {
        $password = 'password-'.Str::random(10);
        $user = User::factory()->create([
            'status' => User::STATUS_ACTIVE,
            'password' => bcrypt($password),
        ]);

        $resp = $this->postJson('/api/auth/login', [
            'email' => $user->email,
            'password' => 'wrong-'.$password,
            'token_name' => 'test',
        ]);

        $resp->assertStatus(401);
        $resp->assertJsonPath('status', 'error');
        $resp->assertJsonPath('code', 'invalid_credentials');
    }
}
