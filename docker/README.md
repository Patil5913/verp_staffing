# Docker

- `build/`  – build & push the image (Dockerfile, apps.json, build.sh). Needs a Gitea read token.
- `deploy/` – run it on a server: `docker-compose.yml`, `.env`, and site scripts
  (`create-site.sh`, `add-app.sh`, `migrate-all.sh`, `backup.sh`, `host-nginx-site.sh`).

Build:   `cd build && GIT_TOKEN=... ./build.sh v0.1.2`
Deploy:  `cd deploy && cp .env.example .env && docker compose up -d && ./create-site.sh tenant.example.com`
Upgrade: set the new tag in `.env`, `docker compose pull && docker compose up -d && ./migrate-all.sh`
