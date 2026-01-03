# Docker Service Template

## Purpose
Add a new microservice to docker-compose.yml following CXFlow patterns.

## Prompt Template

```
Add a new Docker service to docker-compose.yml for [SERVICE_NAME]:

Service Details:
- Name: [SERVICE_NAME]
- Type: [Python/PHP/Node/etc.]
- Port: [PORT]
- Purpose: [DESCRIPTION]

Requirements:
- Include health check endpoint
- Connect to cxflow-network
- Use environment variables from .env
- Add volume mounts for development
- Configure restart policy
- Set proper depends_on with health conditions

Optional:
- Connect to database
- Connect to Redis
- Expose additional ports
```

## Variables to Fill In

- `[SERVICE_NAME]`: Name of the service (e.g., analytics-service)
- `[PORT]`: Port number for the service
- `[DESCRIPTION]`: What the service does

## Example

```
Add a new Docker service to docker-compose.yml for analytics-service:

Service Details:
- Name: analytics-service
- Type: Python FastAPI
- Port: 8200
- Purpose: Real-time analytics processing

Requirements:
- Include health check endpoint at /health
- Connect to cxflow-network
- Use environment variables from .env
- Add volume mounts for development
- Configure restart policy
- Set proper depends_on with health conditions

Optional:
- Connect to Redis for caching
- Mount ./analytics:/app for code
```

## Expected Result

```yaml
# Add to docker-compose.yml
services:
  analytics-service:
    build:
      context: ./analytics
      dockerfile: Dockerfile
    container_name: cxflow_analytics
    ports:
      - "${ANALYTICS_PORT:-8200}:8000"
    environment:
      - SERVICE_NAME=analytics-service
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    volumes:
      - ./analytics:/app
      - analytics-data:/app/data
    networks:
      - cxflow-network
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  analytics-data:
    driver: local

networks:
  cxflow-network:
    driver: bridge
```

## Related Patterns

- See existing services in `docker-compose.yml`
- See `.github/instructions/docker.instructions.md` for Docker patterns
- See `.devcontainer/devcontainer.json` for port configurations

## Follow-up Prompts

1. **Create Dockerfile:**
   ```
   Create a Dockerfile for the analytics service:
   - Multi-stage build
   - Python 3.11 slim base
   - Install dependencies separately
   - Non-root user
   - Health check
   ```

2. **Update Port Configuration:**
   ```
   Update .env.example to include:
   - ANALYTICS_PORT variable
   - Any other service-specific variables
   ```

3. **Register with Gateway:**
   ```
   Show how to register this service with the CXFlow API Gateway
   ```
