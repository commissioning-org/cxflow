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
        Schema::create('superset_dashboards', function (Blueprint $table) {
            $table->id();
            $table->integer('dashboard_id')->unique();
            $table->string('title');
            $table->string('slug')->nullable();
            $table->boolean('published')->default(false);
            $table->json('data')->nullable();
            $table->timestamps();

            $table->index('dashboard_id');
            $table->index('slug');
            $table->index(['published', 'created_at']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('superset_dashboards');
    }
};
