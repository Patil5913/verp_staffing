# Docker

- `build/`  – build & push the image (Dockerfile, apps.json, build.sh). Needs a Gitea read token.
- `deploy/` – run it on a server: `docker-compose.yml`, `.env`, and site scripts
  (`create-site.sh`, `add-app.sh`, `migrate-all.sh`, `backup.sh`, `host-nginx-site.sh`).

Build:   `cd build && GIT_TOKEN=... ./build.sh v0.1.2`
Deploy:  `cd deploy && cp .env.example .env && docker compose up -d && ./create-site.sh tenant.example.com`
Upgrade: set the new tag in `.env`, `docker compose pull && docker compose up -d && ./migrate-all.sh`

Client-hosted database (app stack here, MariaDB on the client's server):
1. On the client server: `cd deploy/client-db && cp .env.example .env` (set root password + VPN IP) `&& docker compose up -d`; firewall the port to our server only.
2. Here: run the stack without the local db: `docker compose -f docker-compose.yml -f docker-compose.remote-db.yml up -d`
3. Create the tenant on that DB: `./create-site.sh client.example.com --db-host <client-vpn-ip> --db-port 3306`
Files (attachments/backups) still live on this server; only the database moves.
