# PHP Laravel Service Template

## Purpose
Create a new Laravel service class following CXFlow project patterns.

## Prompt Template

```
Create a Laravel service class [SERVICE_NAME] for [DESCRIPTION]:

Location: app/Services/[SERVICE_NAME].php

Responsibilities:
- [RESPONSIBILITY_1]
- [RESPONSIBILITY_2]
- [RESPONSIBILITY_3]

Requirements:
- Use constructor dependency injection with readonly properties
- Follow PSR-12 coding standard
- Include proper type hints for all methods
- Use database transactions for data modifications
- Add comprehensive error handling and logging
- Return arrays or objects (not mixed types)
- Include PHPDoc comments

Dependencies:
- [DEPENDENCY_1]
- [DEPENDENCY_2]
```

## Variables to Fill In

- `[SERVICE_NAME]`: Name of the service class (e.g., DataProcessingService)
- `[DESCRIPTION]`: What the service does
- `[RESPONSIBILITY_N]`: Specific responsibilities/methods needed
- `[DEPENDENCY_N]`: Required dependencies to inject

## Example

```
Create a Laravel service class DataProcessingService for processing and validating customer data:

Location: app/Services/DataProcessingService.php

Responsibilities:
- Validate incoming customer data against business rules
- Transform data into standard format
- Save processed data to database
- Trigger events for downstream systems

Requirements:
- Use constructor dependency injection with readonly properties
- Follow PSR-12 coding standard
- Include proper type hints for all methods
- Use database transactions for data modifications
- Add comprehensive error handling and logging
- Return arrays or objects (not mixed types)
- Include PHPDoc comments

Dependencies:
- CustomerRepository
- Logger
- EventDispatcher
```

## Expected Result

```php
<?php

declare(strict_types=1);

namespace App\Services;

use App\Repositories\CustomerRepository;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use App\Events\CustomerDataProcessed;

class DataProcessingService
{
    /**
     * Create a new service instance.
     */
    public function __construct(
        private readonly CustomerRepository $customerRepository,
    ) {}

    /**
     * Process and validate customer data.
     *
     * @param array $data Customer data to process
     * @return array Processed customer data
     * @throws \InvalidArgumentException If validation fails
     * @throws \RuntimeException If processing fails
     */
    public function processCustomerData(array $data): array
    {
        Log::info('Processing customer data', ['customer_id' => $data['id'] ?? 'unknown']);

        try {
            return DB::transaction(function () use ($data) {
                // Validate data
                $validated = $this->validateData($data);
                
                // Transform to standard format
                $transformed = $this->transformData($validated);
                
                // Save to database
                $customer = $this->customerRepository->save($transformed);
                
                // Trigger event
                event(new CustomerDataProcessed($customer));
                
                Log::info('Customer data processed successfully', ['customer_id' => $customer->id]);
                
                return $customer->toArray();
            });
        } catch (\InvalidArgumentException $e) {
            Log::warning('Customer data validation failed', [
                'error' => $e->getMessage(),
                'data' => $data,
            ]);
            throw $e;
        } catch (\Exception $e) {
            Log::error('Customer data processing failed', [
                'error' => $e->getMessage(),
                'data' => $data,
            ]);
            throw new \RuntimeException('Failed to process customer data: ' . $e->getMessage(), 0, $e);
        }
    }

    /**
     * Validate customer data.
     *
     * @param array $data Data to validate
     * @return array Validated data
     * @throws \InvalidArgumentException If validation fails
     */
    private function validateData(array $data): array
    {
        // Validation logic
        if (!isset($data['email']) || !filter_var($data['email'], FILTER_VALIDATE_EMAIL)) {
            throw new \InvalidArgumentException('Invalid email address');
        }
        
        return $data;
    }

    /**
     * Transform data to standard format.
     *
     * @param array $data Data to transform
     * @return array Transformed data
     */
    private function transformData(array $data): array
    {
        // Transformation logic
        return [
            'email' => strtolower($data['email']),
            'name' => ucwords($data['name'] ?? ''),
            'processed_at' => now(),
        ];
    }
}
```

## Related Patterns

- See `src/app/Services/` for existing service examples
- See `.github/instructions/php.instructions.md` for PHP coding standards
- See `src/app/Http/Controllers/` for how services are used in controllers

## Follow-up Prompts

After generating the service:

1. **Add Tests:**
   ```
   Write PHPUnit tests for DataProcessingService:
   - Test successful processing
   - Test validation failures
   - Test transaction rollback
   - Mock dependencies
   - Use RefreshDatabase trait
   ```

2. **Create Controller:**
   ```
   Create a controller that uses DataProcessingService:
   - Inject service via constructor
   - Handle validation with FormRequest
   - Return JSON responses
   - Include error handling
   ```

3. **Add Documentation:**
   ```
   Generate documentation for DataProcessingService:
   - Purpose and responsibilities
   - Method descriptions
   - Usage examples
   - Error handling
   ```
