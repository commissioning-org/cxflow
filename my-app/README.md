# my-app

This is the Laravel application inside the `cxflow` repo.

## API quickstart

### Health

- `GET /api/health` — public, returns `status/data/meta` and includes `X-Request-Id`.

### Authentication (API tokens)

The API uses token authentication via:

`Authorization: Bearer <token>`

Endpoints:

- `POST /api/auth/login` — issues a token (returns the plain token once)
- `GET /api/auth/me` — returns current user (requires token)
- `POST /api/auth/logout` — revokes current token (requires token)

Token abilities are **restricted server-side** based on the user's roles/permissions.

### Protected endpoints

- `GET /api/users` (and related user endpoints) requires:
	- token auth (`auth.token`)
	- ability `api.access`

- `POST /api/assistant/text` and `POST /api/assistant/json` require:
	- token auth (`auth.token`)
	- abilities `api.access` and `assistant.use`

### Token management (self-service)

Requires `api.access`.

- `GET /api/tokens` — list your tokens
- `POST /api/tokens` — create a new token (returns `plain` once)
- `DELETE /api/tokens/{id}` — revoke one of your tokens

## Seeding (RBAC + initial admin)

`DatabaseSeeder` runs `RolesAndPermissionsSeeder` by default.

To control the seeded super admin:

- `ADMIN_EMAIL` (default `admin@example.com`)
- `ADMIN_PASSWORD` (default `password`)

See `.env.example` for the full list.

## Notes

- API responses use a consistent envelope via `App\Support\ApiResponse`.
- Request correlation is handled via `X-Request-Id` middleware.

