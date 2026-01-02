<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Superset Dataset Model
 *
 * Represents a Superset dataset stored locally for caching and tracking.
 *
 * @property int $id
 * @property int $dataset_id
 * @property string $name
 * @property string|null $schema
 * @property array $data
 * @property \Illuminate\Support\Carbon $created_at
 * @property \Illuminate\Support\Carbon $updated_at
 */
final class SupersetDataset extends Model
{
    protected $table = 'superset_datasets';

    protected $fillable = [
        'dataset_id',
        'name',
        'schema',
        'data',
    ];

    protected $casts = [
        'dataset_id' => 'integer',
        'data' => 'array',
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
    ];

    /**
     * Get the database ID for this dataset.
     */
    public function getDatabaseId(): ?int
    {
        return $this->data['database']['id'] ?? null;
    }

    /**
     * Get the full table name with schema.
     */
    public function getFullTableName(): string
    {
        if ($this->schema) {
            return $this->schema . '.' . $this->name;
        }

        return $this->name;
    }

    /**
     * Get columns defined in this dataset.
     */
    public function getColumns(): array
    {
        return $this->data['columns'] ?? [];
    }

    /**
     * Get metrics defined in this dataset.
     */
    public function getMetrics(): array
    {
        return $this->data['metrics'] ?? [];
    }
}
