---
applyTo: "{Dockerfile,docker-compose.yml,**/*.dockerfile}"
---

# Docker & Infrastructure Instructions for CXFlow

## Docker Compose

### Service Definition Pattern

```yaml
services:
  my-service:
    build:
      context: .
      dockerfile: ./path/Dockerfile
    container_name: my_service
    ports:
      - "${SERVICE_PORT:-8000}:8000"
    environment:
      - SERVICE_NAME=my-service
      - DB_HOST=db
    volumes:
      - ./src:/app/src
      - service-data:/app/data
    depends_on:
      db:
        condition: service_healthy
    networks:
      - cxflow-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  service-data:
    driver: local

networks:
  cxflow-network:
    driver: bridge
```

## Dockerfile Best Practices

### Multi-stage Build Pattern

```dockerfile
# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install dependencies in a separate layer
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check using Python (no external dependencies)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### PHP Dockerfile Pattern

```dockerfile
FROM php:8.3-apache

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    libpng-dev \
    libonig-dev \
    libxml2-dev \
    zip \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install PHP extensions
RUN docker-php-ext-install pdo_mysql mbstring exif pcntl bcmath gd

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Enable Apache modules
RUN a2enmod rewrite

# Set working directory
WORKDIR /var/www/html

# Copy application
COPY . .

# Install dependencies
RUN composer install --no-dev --optimize-autoloader

# Set permissions
RUN chown -R www-data:www-data /var/www/html/storage /var/www/html/bootstrap/cache

EXPOSE 80
```

## Service Networking

### Inter-service Communication

Services communicate using Docker service names:

```bash
# In docker-compose.yml
services:
  app:
    environment:
      - DB_HOST=db      # Use service name, not localhost
      - REDIS_HOST=redis
      - ML_SERVICE_URL=http://ml:8000

  db:
    # MySQL service
    
  redis:
    # Redis service
    
  ml:
    # ML microservice
```

### Port Mapping

```yaml
services:
  app:
    ports:
      # External:Internal
      - "${APP_PORT:-8080}:80"      # Web app
      - "${ML_PORT:-8090}:8000"     # ML service
      - "${GATEWAY_PORT:-8100}:8100" # API Gateway
```

## Environment Variables

### .env File Structure

```bash
# Application
APP_PORT=8080
APP_ENV=local
APP_DEBUG=true

# Database
DB_HOST=db
DB_PORT=3306
DB_DATABASE=laravel
DB_USERNAME=laravel
DB_PASSWORD=secret

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Services
ML_PORT=8090
ML_SERVICE_URL=http://ml:8000

# CXFlow Core
GATEWAY_PORT=8100

# Security (never commit real values)
GITHUB_MODELS_TOKEN=your_token_here
SUPABASE_SERVICE_ROLE_KEY=your_key_here
```

### Loading Environment Variables

In docker-compose.yml:

```yaml
services:
  app:
    env_file:
      - .env
    environment:
      - DB_HOST=db
      - DB_DATABASE=${DB_DATABASE:-laravel}
```

## Health Checks

### HTTP Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
  CMD curl -f http://localhost:8000/health || exit 1
```

### Database Health Check

```yaml
services:
  db:
    image: mysql:8.0
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
```

### Custom Health Check Script

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health').raise_for_status()"
```

## Volumes

### Types of Volumes

```yaml
services:
  app:
    volumes:
      # Bind mount for development
      - ./src:/var/www/html/src:cached
      
      # Named volume for persistent data
      - db-data:/var/lib/mysql
      
      # Anonymous volume for cache (excluded from bind mount)
      - /var/www/html/vendor
      - /var/www/html/node_modules

volumes:
  db-data:
    driver: local
```

## Build Context

### Using .dockerignore

```
# .dockerignore
.git
.github
.env
.env.*
node_modules
vendor
*.log
tmp/
.cache/
__pycache__/
*.pyc
.pytest_cache/
coverage/
```

### Multi-service Build

```yaml
services:
  ml:
    build:
      context: ./ml
      dockerfile: Dockerfile
    
  webapp:
    build:
      context: .
      dockerfile: .docker/php/Dockerfile
```

## Development vs Production

### Development Configuration

```yaml
# docker-compose.yml (development)
services:
  app:
    build:
      context: .
      target: development  # Use dev stage
    volumes:
      - ./src:/app/src  # Mount source for hot reload
    environment:
      - DEBUG=true
    command: uvicorn app.main:app --reload --host 0.0.0.0
```

### Production Configuration

```yaml
# docker-compose.prod.yml
services:
  app:
    build:
      context: .
      target: production
    volumes:
      - app-data:/app/data  # Only data volumes
    environment:
      - DEBUG=false
    restart: always
```

## Resource Limits

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## Logging

### Configure Logging Drivers

```yaml
services:
  app:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Security

### Best Practices

1. **Non-root user in containers:**
```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```

2. **Read-only root filesystem:**
```yaml
services:
  app:
    read_only: true
    tmpfs:
      - /tmp
      - /var/run
```

3. **Drop capabilities:**
```yaml
services:
  app:
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

4. **Use secrets for sensitive data:**
```yaml
services:
  app:
    secrets:
      - db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

## Common Commands

```bash
# Build services
docker compose build

# Start services
docker compose up -d

# View logs
docker compose logs -f app

# Execute command in service
docker compose exec app bash

# Stop services
docker compose down

# Remove volumes
docker compose down -v

# View resource usage
docker compose stats

# Validate compose file
docker compose config

# Pull latest images
docker compose pull
```

## Debugging

### Access Container Shell

```bash
docker compose exec app bash
docker compose run --rm app sh
```

### View Logs

```bash
docker compose logs -f app
docker compose logs --tail=100 app
```

### Inspect Network

```bash
docker network ls
docker network inspect cxflow_default
```

### Check Health Status

```bash
docker compose ps
docker inspect --format='{{.State.Health.Status}}' container_name
```

## Common Patterns

### Database Initialization

```yaml
services:
  db:
    image: mysql:8.0
    volumes:
      - db-data:/var/lib/mysql
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
```

### Wait for Dependencies

```yaml
services:
  app:
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
```

### Override for Local Development

Create `docker-compose.override.yml`:

```yaml
# Automatically merged with docker-compose.yml
services:
  app:
    volumes:
      - ./src:/app/src:cached
    environment:
      - DEBUG=true
```

## Common Mistakes to Avoid

1. ❌ Using `localhost` instead of service names
2. ❌ Not using `.dockerignore`
3. ❌ Running containers as root
4. ❌ Not implementing health checks
5. ❌ Hardcoding secrets in Dockerfile
6. ❌ Not using multi-stage builds
7. ❌ Mounting node_modules or vendor directories

## Best Practices

1. ✅ Use multi-stage builds for smaller images
2. ✅ Implement health checks for all services
3. ✅ Use named volumes for persistent data
4. ✅ Run containers as non-root users
5. ✅ Use `.dockerignore` to exclude unnecessary files
6. ✅ Set resource limits
7. ✅ Use service names for inter-service communication
8. ✅ Version your base images (not `latest`)
9. ✅ Configure proper logging
10. ✅ Test with `docker compose config` before deploying
