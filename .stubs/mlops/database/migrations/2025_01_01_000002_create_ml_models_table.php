<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ml_models', function (Blueprint $table) {
            $table->id();
            $table->uuid('model_uuid')->unique();
            $table->uuid('dataset_uuid')->nullable()->index();
            $table->string('automl_model_id')->nullable()->index();
            $table->string('status')->default('candidate'); // candidate|active|archived
            $table->string('problem')->nullable();
            $table->string('metric')->nullable();
            $table->double('score')->nullable();
            $table->json('features')->nullable();
            $table->json('train_result')->nullable();
            $table->json('model_card')->nullable();
            $table->json('meta')->nullable();
            $table->timestamp('trained_at')->nullable();
            $table->timestamp('promoted_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ml_models');
    }
};
