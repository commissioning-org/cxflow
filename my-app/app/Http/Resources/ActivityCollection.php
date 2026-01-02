<?php

declare(strict_types=1);

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\ResourceCollection;

final class ActivityCollection extends ResourceCollection
{
    public $collects = ActivityResource::class;

    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        // Works for paginator instances
        if (method_exists($this->resource, 'total')) {
            return [
                'data' => $this->collection,
                'meta' => [
                    'total' => $this->total(),
                    'per_page' => $this->perPage(),
                    'current_page' => $this->currentPage(),
                    'last_page' => $this->lastPage(),
                    'from' => $this->firstItem(),
                    'to' => $this->lastItem(),
                ],
            ];
        }

        return [
            'data' => $this->collection,
        ];
    }
}
