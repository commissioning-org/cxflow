<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\ApiToken;
use App\Models\User;
use Database\Seeders\RolesAndPermissionsSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

final class ApiTokensTest extends TestCase
{
    use RefreshDatabase;

    public function test_list_tokens_returns_current_users_tokens(): void
    {
        $token = $this->issueTokenForRole(User::ROLE_USER, ['api.access']);

        $resp = $this->withHeader('Authorization', 'Bearer '.$token)->getJson('/api/tokens');

        $resp->assertOk();
        $resp->assertJsonPath('status', 'success');
        $resp->assertJsonStructure([
            'status',
            'data' => ['tokens'],
            'meta' => ['request_id', 'timestamp', 'version'],
        ]);
    }

    public function test_create_token_issues_plain_token_once(): void
    {
        $token = $this->issueTokenForRole(User::ROLE_USER, ['api.access']);

        $resp = $this->withHeader('Authorization', 'Bearer '.$token)->postJson('/api/tokens', [
            'token_name' => 'automation',
            'abilities' => ['api.access', 'assistant.use'], // should be restricted for ROLE_USER
            'expires_in_days' => 7,
        ]);

        $resp->assertCreated();
        $resp->assertJsonPath('status', 'success');

        $plain = (string) $resp->json('data.token.plain');
        $this->assertNotSame('', $plain);

        $issuedAbilities = (array) $resp->json('data.token.abilities');
        $this->assertContains('api.access', $issuedAbilities);
        $this->assertNotContains('assistant.use', $issuedAbilities);

        // Ensure DB token is hashed and not the plain token.
        $this->assertDatabaseHas('api_tokens', [
            'token' => hash('sha256', $plain),
        ]);
    }

    public function test_revoke_token_deletes_it(): void
    {
        $this->seed(RolesAndPermissionsSeeder::class);

        $password = 'password-'.Str::random(10);
        $user = User::factory()->create([
            'status' => User::STATUS_ACTIVE,
            'password' => bcrypt($password),
        ]);
        $user->assignRole(User::ROLE_USER);

        $login = $this->postJson('/api/auth/login', [
            'email' => $user->email,
            'password' => $password,
            'token_name' => 'primary',
            'abilities' => ['api.access'],
        ]);

        $primary = (string) $login->json('data.token.plain');

        $tokenData = ApiToken::generate($user, 'secondary', ['api.access']);
        /** @var ApiToken $secondaryToken */
        $secondaryToken = $tokenData['token'];

        $resp = $this->withHeader('Authorization', 'Bearer '.$primary)->deleteJson('/api/tokens/'.$secondaryToken->id);
        $resp->assertOk();
        $this->assertDatabaseMissing('api_tokens', ['id' => $secondaryToken->id]);
    }

    private function issueTokenForRole(string $role, array $abilities): string
    {
        $this->seed(RolesAndPermissionsSeeder::class);

        $password = 'password-'.Str::random(10);
        $user = User::factory()->create([
            'status' => User::STATUS_ACTIVE,
            'password' => bcrypt($password),
        ]);
        $user->assignRole($role);

        $resp = $this->postJson('/api/auth/login', [
            'email' => $user->email,
            'password' => $password,
            'token_name' => 'test',
            'abilities' => $abilities,
        ]);

        $resp->assertCreated();

        return (string) $resp->json('data.token.plain');
    }
}
