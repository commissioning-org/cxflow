<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use Tests\TestCase;

final class HealthTest extends TestCase
{
    public function test_health_endpoint_returns_request_id_and_success_payload(): void
    {
        $resp = $this->getJson('/api/health');

        $resp->assertOk();
        $resp->assertHeader('X-Request-Id');

        $resp->assertJsonPath('status', 'success');
        $resp->assertJsonPath('data.ok', true);
        $resp->assertJsonStructure([
            'status',
            'data' => ['ok', 'app', 'env'],
            'meta' => ['request_id', 'timestamp', 'version'],
        ]);
    }
}
