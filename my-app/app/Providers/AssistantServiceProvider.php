<?php

declare(strict_types=1);

namespace App\Providers;

use App\Services\Assistant\AssistantClient;
use App\Services\Assistant\AssistantService;
use Illuminate\Support\ServiceProvider;

final class AssistantServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(AssistantClient::class);
        $this->app->singleton(AssistantService::class);
    }
}
