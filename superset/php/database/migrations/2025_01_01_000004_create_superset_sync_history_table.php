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
        Schema::create('superset_sync_history', function (Blueprint $table) {
            $table->id();
            $table->string('resource_type'); // all, dashboards, charts, datasets
            $table->boolean('full_sync')->default(false);
            $table->integer('dashboards_synced')->default(0);
            $table->integer('dashboards_created')->default(0);
            $table->integer('dashboards_updated')->default(0);
            $table->integer('charts_synced')->default(0);
            $table->integer('charts_created')->default(0);
            $table->integer('charts_updated')->default(0);
            $table->integer('datasets_synced')->default(0);
            $table->integer('datasets_created')->default(0);
            $table->integer('datasets_updated')->default(0);
            $table->string('status')->default('completed'); // pending, completed, failed
            $table->text('error_message')->nullable();
            $table->timestamp('started_at');
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();

            $table->index('resource_type');
            $table->index('status');
            $table->index('started_at');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('superset_sync_history');
    }
};
