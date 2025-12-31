# Laravel (LAMP: Apache + MySQL + PHP) — Dockerized Dev Stack

This repository scaffolds a **Linux/Apache/MySQL/PHP** environment tailored for the **Laravel** framework.

## What you get

- **Apache + PHP 8.3** (with `mod_rewrite` enabled and `DocumentRoot` set to `public/`)
- **MySQL 8.0** with healthcheck
- **phpMyAdmin** (optional, enabled by default)
- **Redis** (cache/queue)
- **Mailhog** (SMTP testing + web UI)
- **Queue worker** container (`worker`)
- **Scheduler** container (`scheduler`)
- **Node/Vite** container (`node`) for frontend tooling
- **AutoML microservice** (`ml`) for automated training/prediction (internal)
- Helper scripts to initialize a fresh Laravel app into `./src`

## Quick start

1) Initialize the Laravel app (creates it inside `./src` if missing):

- `bin/init`

> If you want an internal “assistant” integration, `bin/init` will also install a small scaffold into `src/`.

2) (Recommended) Create your local Docker Compose env file:

- Copy `.env.example` to `.env` and set values as needed (especially `GITHUB_MODELS_TOKEN`).

3) Start the stack:

- Foreground: `bin/dev`
- Background: `bin/up`

3) Open in browser:

- App: http://localhost:8080 (or `APP_PORT`)
- phpMyAdmin: http://localhost:8081 (or `PHPMYADMIN_PORT`)
- Mailhog UI: http://localhost:8025 (or `MAILHOG_UI_PORT`)

AutoML service (dev only):

- Health: http://localhost:8090/health (or `ML_PORT`)

## Configuration

Docker Compose reads settings from the repo-root `.env` file (ports, MySQL credentials, optional assistant token).

This repo includes `.env.example`. Your real `.env` is ignored by git.

Laravel’s own environment file will live at:

- `src/.env`

After initialization, update `src/.env` to match your DB settings:

- `DB_HOST=db`
- `DB_PORT=3306`
- `DB_DATABASE=laravel`
- `DB_USERNAME=laravel`
- `DB_PASSWORD=secret`

## SQL Server (sqlsrv) support

This stack also supports **Microsoft SQL Server** (optional):

- The PHP image installs the `sqlsrv` and `pdo_sqlsrv` extensions.
- Docker Compose includes an optional `mssql` service.

### Use SQL Server from Laravel

In `src/.env`, set:

- `DB_CONNECTION=sqlsrv`
- `DB_HOST=mssql`
- `DB_DATABASE=...`
- `DB_USERNAME=sa`
- `DB_PASSWORD=YourStrong!Passw0rd`

Notes:

- SQL Server runs on port `1433` inside the Docker network; `DB_PORT` is often optional for `sqlsrv`.
- The reference repo you shared also mentions that sometimes commenting out `DB_PORT` can help with certain environments; if you hit connectivity issues, try removing `DB_PORT` for `sqlsrv`.

## Internal assistant integration

This scaffold adds (server-side only):

- `config/assistant.php`
- `App\Services\Assistant\AssistantClient`
- `App\Services\Assistant\AssistantService` (caching, retries, JSON helpers)
- `App\Jobs\RunAssistantTask` (queueable automation)
- `php artisan assistant:run` (internal CLI)

### Keep it invisible to end users

Nothing is added to your public routes by default. You call the service from your existing application flows and return your normal UI/API responses.

You should still disclose automated processing where required (privacy policy/terms), but you don’t need to expose provider/model details in responses.

### Secrets stay out of git

Set your token in one of these places:

- Repo root `.env` (picked up by Docker Compose and passed into the app container), **or**
- `src/.env` (Laravel env file)

Do **not** commit real tokens.

By default, the client enforces a single configured model (defaults to `grok-3`) but does not expose the model/provider to end users.

## Common commands

- Install PHP deps: `bin/composer install`
- Run Artisan: `bin/artisan migrate`
- Shell into app container: `bin/shell`
- Tail logs: `bin/logs app` (or `bin/logs worker` / `bin/logs scheduler`)
- Run a one-off queue worker: `bin/queue`
- Run scheduler once: `bin/schedule`
- Frontend tooling: `bin/npm install` or `bin/vite`
- Stop containers: `bin/down`

## AutoML service (internal)

This repo includes an internal Python service in `./ml` that can:

- Train a simple model automatically (tries a small set of common estimators)
- Persist the best model and return a `model_id`
- Run predictions against saved models

Laravel integration stubs:

- `config/automl.php`
- `App\Services\Automl\AutomlClient`
- `App\Jobs\TrainAutomlModel`

Install into `src/` (after Laravel exists):

- `bin/integrate-automl`

## Notes

- This is intended for **local development**.
- For production, you’d typically use a separate deploy setup (real secrets management, TLS, backups, etc.).
