<?php

use App\Http\Controllers\Api\AssistantController;
use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\ApiTokenController;
use App\Http\Controllers\Api\HealthController;
use App\Http\Controllers\Api\UserController;
use Illuminate\Support\Facades\Route;

Route::get('/health', HealthController::class)->name('api.health');

Route::prefix('auth')->name('api.auth.')->group(function (): void {
    Route::post('/login', [AuthController::class, 'login'])
        ->middleware('throttle:10,1')
        ->name('login');

    Route::middleware('auth.token')->group(function (): void {
        Route::get('/me', [AuthController::class, 'me'])->name('me');
        Route::post('/logout', [AuthController::class, 'logout'])->name('logout');
    });
});

Route::middleware(['auth.token', 'ability:api.access'])->group(function (): void {
    Route::prefix('tokens')->name('api.tokens.')->group(function (): void {
        Route::get('/', [ApiTokenController::class, 'index'])->name('index');
        Route::post('/', [ApiTokenController::class, 'store'])->name('store');
        Route::delete('/{token}', [ApiTokenController::class, 'destroy'])->name('destroy');
    });

    Route::prefix('users')->name('api.users.')->group(function (): void {
        Route::get('/', [UserController::class, 'index'])->name('index');
        Route::get('/{user}', [UserController::class, 'show'])->name('show');
        Route::get('/{user}/activities', [UserController::class, 'activities'])->name('activities');
    });

    Route::prefix('assistant')->name('api.assistant.')->middleware('ability:assistant.use')->group(function (): void {
        Route::post('/text', [AssistantController::class, 'text'])->name('text');
        Route::post('/json', [AssistantController::class, 'json'])->name('json');
    });
});
