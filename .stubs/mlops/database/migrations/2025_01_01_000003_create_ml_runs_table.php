<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ml_runs', function (Blueprint $table) {
            $table->id();
            $table->uuid('run_uuid')->unique();
            $table->string('pipeline')->nullable();
            $table->string('kind')->default('train');
            $table->string('status')->default('completed');
            $table->json('payload')->nullable();
            $table->json('result')->nullable();
            $table->text('error')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ml_runs');
    }
};
