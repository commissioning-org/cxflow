<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class MlRun extends Model
{
    protected $table = 'ml_runs';

    protected $guarded = [];

    protected $casts = [
        'payload' => 'array',
        'result' => 'array',
    ];
}
