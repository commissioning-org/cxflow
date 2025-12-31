<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ml_datasets', function (Blueprint $table) {
            $table->id();
            $table->uuid('dataset_uuid')->unique();
            $table->string('name')->nullable();
            $table->string('source')->nullable();
            $table->json('schema')->nullable();
            $table->unsignedInteger('row_count')->nullable();
            $table->string('target')->nullable();
            $table->json('meta')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ml_datasets');
    }
};
