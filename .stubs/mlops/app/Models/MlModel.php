<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class MlModel extends Model
{
    protected $table = 'ml_models';

    protected $guarded = [];

    protected $casts = [
        'features' => 'array',
        'train_result' => 'array',
        'model_card' => 'array',
        'meta' => 'array',
    ];
}
