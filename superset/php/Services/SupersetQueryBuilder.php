<?php

declare(strict_types=1);

namespace App\Services\Superset;

/**
 * Superset Query Builder
 *
 * Fluent interface for building Superset query contexts.
 */
final class SupersetQueryBuilder
{
    private array $query = [
        'columns' => [],
        'metrics' => [],
        'filters' => [],
        'row_limit' => 1000,
        'row_offset' => 0,
        'order_by' => [],
        'granularity_sqla' => null,
        'time_range' => null,
    ];

    public function __construct(
        private ?int $datasourceId = null,
        private string $datasourceType = 'table'
    ) {
    }

    /**
     * Set the datasource.
     */
    public function datasource(int $id, string $type = 'table'): self
    {
        $this->datasourceId = $id;
        $this->datasourceType = $type;
        return $this;
    }

    /**
     * Add columns to select.
     */
    public function columns(array $columns): self
    {
        $this->query['columns'] = array_merge($this->query['columns'], $columns);
        return $this;
    }

    /**
     * Add a single column.
     */
    public function column(string $column): self
    {
        $this->query['columns'][] = $column;
        return $this;
    }

    /**
     * Add metrics to compute.
     */
    public function metrics(array $metrics): self
    {
        $this->query['metrics'] = array_merge($this->query['metrics'], $metrics);
        return $this;
    }

    /**
     * Add a single metric.
     */
    public function metric(string|array $metric): self
    {
        $this->query['metrics'][] = $metric;
        return $this;
    }

    /**
     * Add count metric.
     */
    public function count(string $column = '*', ?string $label = null): self
    {
        $this->query['metrics'][] = [
            'expressionType' => 'SQL',
            'sqlExpression' => "COUNT({$column})",
            'label' => $label ?? "count_{$column}",
        ];
        return $this;
    }

    /**
     * Add sum metric.
     */
    public function sum(string $column, ?string $label = null): self
    {
        $this->query['metrics'][] = [
            'expressionType' => 'SQL',
            'sqlExpression' => "SUM({$column})",
            'label' => $label ?? "sum_{$column}",
        ];
        return $this;
    }

    /**
     * Add average metric.
     */
    public function avg(string $column, ?string $label = null): self
    {
        $this->query['metrics'][] = [
            'expressionType' => 'SQL',
            'sqlExpression' => "AVG({$column})",
            'label' => $label ?? "avg_{$column}",
        ];
        return $this;
    }

    /**
     * Add filters.
     */
    public function filters(array $filters): self
    {
        $this->query['filters'] = array_merge($this->query['filters'], $filters);
        return $this;
    }

    /**
     * Add a WHERE filter.
     */
    public function where(string $column, string $operator, mixed $value): self
    {
        $this->query['filters'][] = [
            'col' => $column,
            'op' => $operator,
            'val' => $value,
        ];
        return $this;
    }

    /**
     * Add equals filter.
     */
    public function whereEquals(string $column, mixed $value): self
    {
        return $this->where($column, '==', $value);
    }

    /**
     * Add IN filter.
     */
    public function whereIn(string $column, array $values): self
    {
        return $this->where($column, 'IN', $values);
    }

    /**
     * Add LIKE filter.
     */
    public function whereLike(string $column, string $value): self
    {
        return $this->where($column, 'LIKE', $value);
    }

    /**
     * Set row limit.
     */
    public function limit(int $limit): self
    {
        $this->query['row_limit'] = $limit;
        return $this;
    }

    /**
     * Set row offset.
     */
    public function offset(int $offset): self
    {
        $this->query['row_offset'] = $offset;
        return $this;
    }

    /**
     * Add ordering.
     */
    public function orderBy(string $column, bool $ascending = true): self
    {
        $this->query['order_by'][] = [$column, $ascending];
        return $this;
    }

    /**
     * Set time column for time-series queries.
     */
    public function timeColumn(string $column): self
    {
        $this->query['granularity_sqla'] = $column;
        return $this;
    }

    /**
     * Set time range.
     */
    public function timeRange(string $range): self
    {
        $this->query['time_range'] = $range;
        return $this;
    }

    /**
     * Set time range using dates.
     */
    public function timeBetween(string $start, string $end): self
    {
        $this->query['time_range'] = "{$start} : {$end}";
        return $this;
    }

    /**
     * Set relative time range.
     */
    public function last(int $value, string $unit): self
    {
        $this->query['time_range'] = "Last {$value} {$unit}";
        return $this;
    }

    /**
     * Group by columns.
     */
    public function groupBy(array $columns): self
    {
        $this->query['groupby'] = $columns;
        return $this;
    }

    /**
     * Build the query context.
     */
    public function build(): array
    {
        $context = [
            'datasource' => [
                'id' => $this->datasourceId,
                'type' => $this->datasourceType,
            ],
            'queries' => [$this->query],
        ];

        return $context;
    }

    /**
     * Get the raw query array.
     */
    public function toArray(): array
    {
        return $this->query;
    }

    /**
     * Create a new query builder instance.
     */
    public static function make(?int $datasourceId = null): self
    {
        return new self($datasourceId);
    }
}
