---
applyTo: "**/*.php"
---

# PHP/Laravel Code Instructions for CXFlow

## Style & Standards

- Follow **PSR-12** coding standard
- Use **PHP 8.3** features (named arguments, readonly properties, enums)
- Type hints for all parameters and return types
- Use **strict types** declaration at the top of files
- Opening brace on same line for methods, next line for classes
- 4 spaces for indentation (no tabs)

## File Structure

Every PHP file should start with:

```php
<?php

declare(strict_types=1);

namespace App\Services\MyNamespace;

use Illuminate\Support\Facades\Log;
use App\Models\User;
```

## Laravel Conventions

### Directory Structure

- **Models**: `app/Models/` - Eloquent models
- **Controllers**: `app/Http/Controllers/` - HTTP request handlers
- **Services**: `app/Services/` - Business logic
- **Jobs**: `app/Jobs/` - Queue jobs
- **Commands**: `app/Console/Commands/` - Artisan commands
- **Middleware**: `app/Http/Middleware/`
- **Requests**: `app/Http/Requests/` - Form request validation
- **Resources**: `app/Http/Resources/` - API resources

### Models

Use Eloquent ORM features properly:

```php
<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Factories\HasFactory;

class MyModel extends Model
{
    use HasFactory;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'name',
        'email',
        'status',
    ];

    /**
     * The attributes that should be cast.
     */
    protected $casts = [
        'is_active' => 'boolean',
        'metadata' => 'array',
        'created_at' => 'datetime',
    ];

    /**
     * Get the related items.
     */
    public function items(): HasMany
    {
        return $this->hasMany(Item::class);
    }
}
```

### Controllers

Keep controllers thin - delegate to services:

```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Services\DataService;
use App\Http\Requests\StoreDataRequest;
use App\Http\Resources\DataResource;
use Illuminate\Http\JsonResponse;

class DataController extends Controller
{
    public function __construct(
        private readonly DataService $dataService
    ) {}

    /**
     * Store new data.
     */
    public function store(StoreDataRequest $request): JsonResponse
    {
        $data = $this->dataService->create($request->validated());
        
        return response()->json(
            new DataResource($data),
            201
        );
    }
}
```

### Services

Business logic goes in service classes:

```php
<?php

declare(strict_types=1);

namespace App\Services;

use App\Models\MyModel;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

class MyService
{
    public function __construct(
        private readonly ExternalService $externalService
    ) {}

    /**
     * Process the data with transaction safety.
     */
    public function processData(array $data): MyModel
    {
        return DB::transaction(function () use ($data) {
            $model = MyModel::create($data);
            
            $this->externalService->notify($model);
            
            Log::info('Data processed', ['id' => $model->id]);
            
            return $model;
        });
    }
}
```

### Jobs (Queue)

Use jobs for background processing:

```php
<?php

declare(strict_types=1);

namespace App\Jobs;

use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;

class ProcessDataJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    /**
     * The number of times the job may be attempted.
     */
    public int $tries = 3;

    /**
     * The number of seconds to wait before retrying.
     */
    public int $backoff = 60;

    /**
     * Create a new job instance.
     */
    public function __construct(
        public readonly array $data,
        public readonly string $userId
    ) {}

    /**
     * Execute the job.
     */
    public function handle(MyService $service): void
    {
        Log::info('Processing job', ['user_id' => $this->userId]);
        
        $service->process($this->data);
    }

    /**
     * Handle a job failure.
     */
    public function failed(\Throwable $exception): void
    {
        Log::error('Job failed', [
            'user_id' => $this->userId,
            'error' => $exception->getMessage(),
        ]);
    }
}
```

### Artisan Commands

Create commands for CLI operations:

```php
<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use App\Services\MyService;

class ProcessCommand extends Command
{
    /**
     * The name and signature of the console command.
     */
    protected $signature = 'process:data {source : The data source} {--async : Run asynchronously}';

    /**
     * The console command description.
     */
    protected $description = 'Process data from the specified source';

    /**
     * Execute the console command.
     */
    public function handle(MyService $service): int
    {
        $source = $this->argument('source');
        $async = $this->option('async');

        $this->info("Processing data from: {$source}");
        
        try {
            $result = $service->processSource($source, $async);
            $this->info("Processed {$result['count']} items");
            return Command::SUCCESS;
        } catch (\Exception $e) {
            $this->error("Error: {$e->getMessage()}");
            return Command::FAILURE;
        }
    }
}
```

## Dependency Injection

Always use constructor injection:

```php
<?php

// Good - Constructor injection
class MyService
{
    public function __construct(
        private readonly Repository $repo,
        private readonly Logger $logger
    ) {}
}

// Avoid facades when testing is important
// Use contracts/interfaces instead
use Illuminate\Contracts\Cache\Repository as CacheContract;

class CachedService
{
    public function __construct(
        private readonly CacheContract $cache
    ) {}
}
```

## Database

### Migrations

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('my_table', function (Blueprint $table) {
            $table->id();
            $table->string('name');
            $table->text('description')->nullable();
            $table->boolean('is_active')->default(true);
            $table->json('metadata')->nullable();
            $table->timestamps();
            
            $table->index('name');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('my_table');
    }
};
```

### Query Builder

Use query builder efficiently:

```php
<?php

// Good - Efficient queries
$users = DB::table('users')
    ->where('active', true)
    ->where('created_at', '>=', now()->subDays(30))
    ->orderBy('name')
    ->get();

// Use eager loading to avoid N+1
$posts = Post::with(['author', 'comments.user'])->get();

// Use chunks for large datasets
DB::table('logs')
    ->where('created_at', '<', now()->subDays(90))
    ->chunkById(1000, function ($logs) {
        // Process chunk
    });
```

## Error Handling

```php
<?php

use Illuminate\Support\Facades\Log;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Validation\ValidationException;

try {
    $model = MyModel::findOrFail($id);
    $result = $this->process($model);
} catch (ModelNotFoundException $e) {
    Log::warning('Model not found', ['id' => $id]);
    return response()->json(['error' => 'Not found'], 404);
} catch (ValidationException $e) {
    return response()->json(['errors' => $e->errors()], 422);
} catch (\Exception $e) {
    Log::error('Processing failed', [
        'id' => $id,
        'error' => $e->getMessage(),
        'trace' => $e->getTraceAsString(),
    ]);
    return response()->json(['error' => 'Internal error'], 500);
}
```

## Configuration

Always use config files, never hardcode values:

```php
<?php

// Good - Use config
$apiUrl = config('services.external.url');
$timeout = config('services.external.timeout', 30);

// Use env() only in config files
// config/services.php
return [
    'external' => [
        'url' => env('EXTERNAL_API_URL'),
        'token' => env('EXTERNAL_API_TOKEN'),
    ],
];
```

## Validation

Use Form Requests for validation:

```php
<?php

declare(strict_types=1);

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreDataRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // Or check permissions
    }

    public function rules(): array
    {
        return [
            'name' => ['required', 'string', 'max:255'],
            'email' => ['required', 'email', 'unique:users'],
            'age' => ['required', 'integer', 'min:18', 'max:120'],
            'tags' => ['array'],
            'tags.*' => ['string', 'max:50'],
        ];
    }

    public function messages(): array
    {
        return [
            'email.unique' => 'This email is already registered.',
            'age.min' => 'You must be at least 18 years old.',
        ];
    }
}
```

## Testing

Write tests for all features:

```php
<?php

declare(strict_types=1);

namespace Tests\Feature;

use Tests\TestCase;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;

class DataControllerTest extends TestCase
{
    use RefreshDatabase;

    public function test_user_can_create_data(): void
    {
        $user = User::factory()->create();
        
        $response = $this->actingAs($user)
            ->postJson('/api/data', [
                'name' => 'Test',
                'value' => 123,
            ]);

        $response->assertStatus(201)
            ->assertJson(['name' => 'Test']);
            
        $this->assertDatabaseHas('data', [
            'name' => 'Test',
            'user_id' => $user->id,
        ]);
    }
}
```

## Docker Environment

Remember when working in Docker:

```php
<?php

// Database connection uses Docker service name
DB_HOST=db  // Not localhost
DB_PORT=3306

// Redis connection
REDIS_HOST=redis
REDIS_PORT=6379

// Mail (Mailhog)
MAIL_HOST=mailhog
MAIL_PORT=1025
```

## Assistant Integration

For internal AI assistance:

```php
<?php

use App\Services\Assistant\AssistantService;

class MyService
{
    public function __construct(
        private readonly AssistantService $assistant
    ) {}

    public function analyzeData(array $data): array
    {
        // Use assistant for server-side processing
        $analysis = $this->assistant->analyze($data, [
            'template' => 'data-analysis',
            'context' => ['type' => 'metrics'],
        ]);
        
        // Return processed results (not AI provider details)
        return [
            'summary' => $analysis['summary'],
            'insights' => $analysis['insights'],
        ];
    }
}
```

## Ingestion Scripts Pattern

For standalone PHP scripts in `ingestion/`:

```php
<?php

declare(strict_types=1);

// Load environment
$envFile = __DIR__ . '/../.env';
if (file_exists($envFile)) {
    $lines = file($envFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        if (strpos(trim($line), '#') === 0) {
            continue;
        }
        putenv($line);
    }
}

// Configuration
$config = [
    'enabled' => getenv('CX_FEATURE_ENABLED') === 'true',
    'timeout' => (int) (getenv('CX_TIMEOUT') ?: 30),
];

// Error handling
set_error_handler(function ($severity, $message, $file, $line) {
    throw new ErrorException($message, 0, $severity, $file, $line);
});

// Main logic
try {
    $result = processIngestion($config);
    echo json_encode($result, JSON_PRETTY_PRINT);
    exit(0);
} catch (Throwable $e) {
    error_log("Error: {$e->getMessage()}");
    echo json_encode(['error' => $e->getMessage()]);
    exit(1);
}
```

## Common Mistakes to Avoid

1. ❌ Don't use `DB_HOST=localhost` in Docker (use `db`)
2. ❌ Don't put business logic in controllers
3. ❌ Don't use `env()` outside config files
4. ❌ Don't forget to use database transactions for multi-step operations
5. ❌ Don't ignore N+1 query problems - use eager loading
6. ❌ Don't hardcode secrets or API keys
7. ❌ Don't mix synchronous and queue operations without clear separation

## Best Practices

1. ✅ Use dependency injection
2. ✅ Type hint everything
3. ✅ Use readonly properties for immutable data
4. ✅ Write tests for all features
5. ✅ Use Form Requests for validation
6. ✅ Log important operations
7. ✅ Use database transactions for data integrity
8. ✅ Cache expensive operations
9. ✅ Use queues for long-running tasks
10. ✅ Keep controllers thin, services fat
