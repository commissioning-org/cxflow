<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class MlDataset extends Model
{
    protected $table = 'ml_datasets';

    protected $guarded = [];

    protected $casts = [
        'schema' => 'array',
        'meta' => 'array',
    ];
}
