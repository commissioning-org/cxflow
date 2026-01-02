<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('superset_datasets', function (Blueprint $table) {
            $table->id();
            $table->integer('dataset_id')->unique();
            $table->string('name');
            $table->string('schema')->nullable();
            $table->json('data')->nullable();
            $table->timestamps();

            $table->index('dataset_id');
            $table->index(['schema', 'name']);
            $table->index('created_at');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('superset_datasets');
    }
};
