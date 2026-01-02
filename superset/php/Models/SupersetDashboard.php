<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Superset Dashboard Model
 *
 * Represents a Superset dashboard stored locally for caching and tracking.
 *
 * @property int $id
 * @property int $dashboard_id
 * @property string $title
 * @property string|null $slug
 * @property bool $published
 * @property array $data
 * @property \Illuminate\Support\Carbon $created_at
 * @property \Illuminate\Support\Carbon $updated_at
 */
final class SupersetDashboard extends Model
{
    protected $table = 'superset_dashboards';

    protected $fillable = [
        'dashboard_id',
        'title',
        'slug',
        'published',
        'data',
    ];

    protected $casts = [
        'dashboard_id' => 'integer',
        'published' => 'boolean',
        'data' => 'array',
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
    ];

    /**
     * Get charts associated with this dashboard.
     */
    public function charts(): array
    {
        $chartIds = [];
        $metadata = $this->data['metadata'] ?? [];

        if (is_string($metadata)) {
            $metadata = json_decode($metadata, true) ?? [];
        }

        $chartsInDashboard = $metadata['charts'] ?? [];
        foreach ($chartsInDashboard as $chartId) {
            if (is_numeric($chartId)) {
                $chartIds[] = (int) $chartId;
            }
        }

        return SupersetChart::whereIn('chart_id', $chartIds)->get()->toArray();
    }

    /**
     * Get the dashboard URL.
     */
    public function getUrl(string $baseUrl): string
    {
        return rtrim($baseUrl, '/') . '/superset/dashboard/' . $this->dashboard_id . '/';
    }

    /**
     * Get the embedded dashboard URL.
     */
    public function getEmbedUrl(string $baseUrl, bool $standalone = true): string
    {
        $url = $this->getUrl($baseUrl);

        if ($standalone) {
            $url .= '?standalone=1';
        }

        return $url;
    }
}
