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
        Schema::create('superset_charts', function (Blueprint $table) {
            $table->id();
            $table->integer('chart_id')->unique();
            $table->string('name');
            $table->string('viz_type')->nullable();
            $table->json('data')->nullable();
            $table->timestamps();

            $table->index('chart_id');
            $table->index('viz_type');
            $table->index('created_at');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('superset_charts');
    }
};
