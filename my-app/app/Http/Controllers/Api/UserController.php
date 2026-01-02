<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Http\Requests\Api\ListUsersRequest;
use App\Http\Resources\ActivityCollection;
use App\Http\Resources\UserCollection;
use App\Http\Resources\UserResource;
use App\Models\Activity;
use App\Models\User;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\Request;

final class UserController extends ApiController
{
    public function index(ListUsersRequest $request): UserCollection
    {
        $query = User::query();

        $validated = $request->validated();

        if (isset($validated['q']) && is_string($validated['q']) && $validated['q'] !== '') {
            $q = $validated['q'];
            $query->where(function (Builder $qBuilder) use ($q): void {
                $qBuilder
                    ->where('name', 'like', "%{$q}%")
                    ->orWhere('email', 'like', "%{$q}%")
                    ->orWhere('phone', 'like', "%{$q}%");
            });
        }

        if (isset($validated['status']) && is_string($validated['status']) && $validated['status'] !== '') {
            $query->where('status', $validated['status']);
        }

        if (isset($validated['role']) && is_string($validated['role']) && $validated['role'] !== '') {
            $role = $validated['role'];
            $query->whereHas('roles', fn (Builder $q) => $q->where('name', $role));
        }

        $includes = $request->includes();
        if (in_array('roles', $includes, true)) {
            $query->with('roles');
        }

        $sort = (string) ($validated['sort'] ?? '-created_at');
        [$sortColumn, $sortDir] = $this->parseSort($sort);
        $query->orderBy($sortColumn, $sortDir);

        $perPage = (int) ($validated['per_page'] ?? 15);
        $users = $query->paginate($perPage);

        return new UserCollection($users);
    }

    public function show(Request $request, User $user): UserResource
    {
        $user->loadMissing('roles');

        return new UserResource($user);
    }

    public function activities(Request $request, User $user): ActivityCollection
    {
        $this->authorize('viewActivity', $user);

        $perPage = (int) $request->integer('per_page', 20);
        $perPage = max(1, min(100, $perPage));

        $items = Activity::query()
            ->where('user_id', $user->id)
            ->latest()
            ->paginate($perPage);

        return new ActivityCollection($items);
    }

    /**
     * @return array{0: string, 1: 'asc'|'desc'}
     */
    private function parseSort(string $sort): array
    {
        $allowed = ['id', 'name', 'email', 'status', 'created_at', 'last_login_at'];

        $dir = 'asc';
        $col = trim($sort);
        if (str_starts_with($col, '-')) {
            $dir = 'desc';
            $col = ltrim($col, '-');
        }

        if (!in_array($col, $allowed, true)) {
            $col = 'created_at';
            $dir = 'desc';
        }

        return [$col, $dir];
    }
}
