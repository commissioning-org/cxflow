<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Superset Chart Model
 *
 * Represents a Superset chart stored locally for caching and tracking.
 *
 * @property int $id
 * @property int $chart_id
 * @property string $name
 * @property string|null $viz_type
 * @property array $data
 * @property \Illuminate\Support\Carbon $created_at
 * @property \Illuminate\Support\Carbon $updated_at
 */
final class SupersetChart extends Model
{
    protected $table = 'superset_charts';

    protected $fillable = [
        'chart_id',
        'name',
        'viz_type',
        'data',
    ];

    protected $casts = [
        'chart_id' => 'integer',
        'data' => 'array',
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
    ];

    /**
     * Get the dataset associated with this chart.
     */
    public function dataset(): ?SupersetDataset
    {
        $datasetId = $this->data['datasource_id'] ?? null;

        if (!$datasetId) {
            return null;
        }

        return SupersetDataset::where('dataset_id', $datasetId)->first();
    }

    /**
     * Get the chart type display name.
     */
    public function getVizTypeDisplayName(): string
    {
        return match ($this->viz_type) {
            'table' => 'Table',
            'big_number' => 'Big Number',
            'big_number_total' => 'Big Number with Trendline',
            'line' => 'Line Chart',
            'bar' => 'Bar Chart',
            'area' => 'Area Chart',
            'pie' => 'Pie Chart',
            'scatter' => 'Scatter Plot',
            'bubble' => 'Bubble Chart',
            'heatmap' => 'Heatmap',
            'box_plot' => 'Box Plot',
            'treemap' => 'Treemap',
            'sunburst' => 'Sunburst',
            'sankey' => 'Sankey Diagram',
            'word_cloud' => 'Word Cloud',
            'country_map' => 'Country Map',
            default => $this->viz_type ?? 'Unknown',
        };
    }
}
