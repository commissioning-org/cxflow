---
applyTo: "**/*.{js,jsx,ts,tsx}"
---

# JavaScript/TypeScript Instructions for CXFlow

## Style & Standards

- Use **TypeScript** for all new code
- Follow **ESLint** and **Prettier** configurations
- Use **ES6+** features (arrow functions, destructuring, async/await)
- Prefer `const` over `let`, avoid `var`
- Use template literals for string interpolation
- Maximum line length: 100 characters

## TypeScript Conventions

Always use TypeScript with strict typing:

```typescript
// Good - Full type definitions
interface User {
  id: number;
  name: string;
  email: string;
  isActive: boolean;
  metadata?: Record<string, unknown>;
}

function processUser(user: User): { status: string; data: User } {
  // Implementation
  return { status: 'success', data: user };
}

// Not this - Avoid 'any'
function processUser(user: any): any {
  // Bad - no type safety
}
```

## Naming Conventions

- **Variables & Functions**: camelCase (`myFunction`, `userData`)
- **Classes & Interfaces**: PascalCase (`UserService`, `DataModel`)
- **Constants**: UPPER_SNAKE_CASE (`API_BASE_URL`, `MAX_RETRIES`)
- **Private properties**: prefix with `_` or use TypeScript `private`
- **Boolean variables**: prefix with `is`, `has`, `should` (`isActive`, `hasData`)

## Module Exports

Use named exports for better refactoring:

```typescript
// Good - Named exports
export const API_URL = 'https://api.example.com';
export function fetchData(id: string): Promise<Data> { ... }
export class DataService { ... }

// Avoid default exports unless it's a React component
export default function HomePage() { ... } // OK for React
```

## Async/Await

Always use async/await for promises:

```typescript
// Good
async function fetchUserData(userId: string): Promise<User> {
  try {
    const response = await fetch(`/api/users/${userId}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Failed to fetch user:', error);
    throw error;
  }
}

// Not this - Promise chains
function fetchUserData(userId) {
  return fetch(`/api/users/${userId}`)
    .then(response => response.json())
    .catch(error => console.error(error));
}
```

## Error Handling

Use proper error handling with types:

```typescript
class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public response?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function apiCall(endpoint: string): Promise<Data> {
  try {
    const response = await fetch(endpoint);
    
    if (!response.ok) {
      throw new ApiError(
        'API request failed',
        response.status,
        await response.json()
      );
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      console.error(`API Error ${error.statusCode}:`, error.message);
    } else if (error instanceof TypeError) {
      console.error('Network error:', error.message);
    } else {
      console.error('Unexpected error:', error);
    }
    throw error;
  }
}
```

## React/JSX (if applicable)

Follow React best practices:

```typescript
import React, { useState, useEffect, useCallback } from 'react';

interface DataDisplayProps {
  userId: string;
  onError?: (error: Error) => void;
}

export function DataDisplay({ userId, onError }: DataDisplayProps) {
  const [data, setData] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const userData = await fetchUserData(userId);
      setData(userData);
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [userId, onError]);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  if (loading) return <div>Loading...</div>;
  if (!data) return <div>No data</div>;
  
  return (
    <div>
      <h2>{data.name}</h2>
      <p>{data.email}</p>
    </div>
  );
}
```

## Functional Programming

Prefer functional patterns:

```typescript
// Good - Functional approach
const activeUsers = users
  .filter(user => user.isActive)
  .map(user => ({ id: user.id, name: user.name }))
  .sort((a, b) => a.name.localeCompare(b.name));

// Use reduce for aggregations
const totalValue = items.reduce((sum, item) => sum + item.value, 0);

// Avoid mutations
const updatedUser = { ...user, name: 'New Name' }; // Good
user.name = 'New Name'; // Avoid
```

## Object Destructuring

Use destructuring for cleaner code:

```typescript
// Good
const { id, name, email } = user;
const { data, loading, error } = useQuery();

// Function parameters
function createUser({ name, email, age }: UserInput) {
  // Implementation
}

// Array destructuring
const [first, second, ...rest] = items;
```

## Type Guards

Use type guards for safe type narrowing:

```typescript
interface Cat {
  type: 'cat';
  meow(): void;
}

interface Dog {
  type: 'dog';
  bark(): void;
}

type Animal = Cat | Dog;

function isCat(animal: Animal): animal is Cat {
  return animal.type === 'cat';
}

function handleAnimal(animal: Animal) {
  if (isCat(animal)) {
    animal.meow(); // TypeScript knows this is a Cat
  } else {
    animal.bark(); // TypeScript knows this is a Dog
  }
}
```

## API Client Pattern

Create typed API clients:

```typescript
class ApiClient {
  constructor(private baseUrl: string) {}
  
  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
    
    if (!response.ok) {
      throw new ApiError('Request failed', response.status);
    }
    
    return response.json();
  }
  
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint);
  }
  
  async post<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

// Usage
const client = new ApiClient('/api');
const users = await client.get<User[]>('/users');
```

## Environment Variables

Access environment variables properly:

```typescript
// For Vite
const apiUrl = import.meta.env.VITE_API_URL;

// For Next.js
const apiUrl = process.env.NEXT_PUBLIC_API_URL;

// Always provide defaults and validate
const config = {
  apiUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: Number(import.meta.env.VITE_TIMEOUT) || 30000,
};

// Type-safe environment variables
interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_TIMEOUT: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

## Testing

Write tests with Jest/Vitest:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { DataDisplay } from './DataDisplay';

describe('DataDisplay', () => {
  it('displays user data when loaded', async () => {
    const mockUser = { id: '1', name: 'John', email: 'john@example.com' };
    
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockUser,
    });
    
    render(<DataDisplay userId="1" />);
    
    await waitFor(() => {
      expect(screen.getByText('John')).toBeInTheDocument();
    });
  });
  
  it('calls onError when fetch fails', async () => {
    const onError = vi.fn();
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
    
    render(<DataDisplay userId="1" onError={onError} />);
    
    await waitFor(() => {
      expect(onError).toHaveBeenCalled();
    });
  });
});
```

## Utility Functions

Create reusable utilities:

```typescript
// Type-safe utility functions
export function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${value}`);
}

export function isDefined<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined;
}

export function groupBy<T>(
  items: T[],
  keyFn: (item: T) => string
): Record<string, T[]> {
  return items.reduce((groups, item) => {
    const key = keyFn(item);
    return {
      ...groups,
      [key]: [...(groups[key] || []), item],
    };
  }, {} as Record<string, T[]>);
}
```

## Common Mistakes to Avoid

1. ❌ Using `any` type - always use proper types
2. ❌ Mutating state directly in React
3. ❌ Not handling promise rejections
4. ❌ Using `var` instead of `const`/`let`
5. ❌ Ignoring null/undefined checks
6. ❌ Not using TypeScript strict mode
7. ❌ Forgetting to clean up useEffect hooks

## Best Practices

1. ✅ Use TypeScript strict mode
2. ✅ Always handle errors in async functions
3. ✅ Use const by default, let when necessary
4. ✅ Prefer functional programming patterns
5. ✅ Use meaningful variable names
6. ✅ Keep functions small and focused
7. ✅ Write tests for critical functionality
8. ✅ Use ESLint and Prettier
9. ✅ Avoid deep nesting - use early returns
10. ✅ Document complex logic with comments

## Quick Reference: Common Cookbook Patterns

### Create API Client
**Prompt:**
```
Create a type-safe API client for Laravel backend:
- Use fetch with proper types
- Handle CSRF token
- Include error handling
- Return typed responses
```

### React Component
**Prompt:**
```
Create a React component for displaying data:
- Use TypeScript with proper types
- Fetch data with useEffect
- Handle loading and error states
- Include proper error boundaries
```

### Form Validation
**Prompt:**
```
Create a form with validation:
- Use controlled components
- Validate on submit
- Display error messages
- Handle async submission
```

### API Integration
**Prompt:**
```
Integrate with backend API:
- Type-safe requests/responses
- Handle authentication
- Retry on failure
- Loading states
```

### Write Tests
**Prompt:**
```
Write tests for this component:
- Test rendering
- Test user interactions
- Mock API calls
- Test error states
```

For more prompts, see: [docs/COPILOT_COOKBOOK_EXAMPLES.md](../../docs/COPILOT_COOKBOOK_EXAMPLES.md)

## Integration with Backend

When calling Laravel backend:

```typescript
// CSRF token for Laravel
const csrfToken = document.querySelector('meta[name="csrf-token"]')
  ?.getAttribute('content');

async function laravelRequest(endpoint: string, data: unknown) {
  return fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-TOKEN': csrfToken || '',
      'Accept': 'application/json',
    },
    body: JSON.stringify(data),
  });
}
```

