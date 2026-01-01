<?php

declare(strict_types=1);

namespace App\Services\Superset;

use Illuminate\Support\ServiceProvider;

/**
 * Superset Service Provider
 *
 * Registers Superset services with Laravel.
 *
 * @package App\Services\Superset
 */
class SupersetServiceProvider extends ServiceProvider
{
    /**
     * Register services.
     */
    public function register(): void
    {
        $this->mergeConfigFrom(
            __DIR__ . '/config/superset.php',
            'superset'
        );

        $this->app->singleton(SupersetClient::class, function ($app) {
            return new SupersetClient(
                config('superset.base_url'),
                config('superset.username'),
                config('superset.password')
            );
        });

        $this->app->alias(SupersetClient::class, 'superset');
    }

    /**
     * Bootstrap services.
     */
    public function boot(): void
    {
        if ($this->app->runningInConsole()) {
            $this->publishes([
                __DIR__ . '/config/superset.php' => config_path('superset.php'),
            ], 'superset-config');
        }
    }

    /**
     * Get the services provided by the provider.
     */
    public function provides(): array
    {
        return [
            SupersetClient::class,
            'superset',
        ];
    }
}
