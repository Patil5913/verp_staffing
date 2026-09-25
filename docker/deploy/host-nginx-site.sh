#!/bin/bash
# Run on the HOST as root (not in a container). Publishes one tenant domain
# through the host's nginx + certbot, forwarding to the Docker stack.
#   sudo ./host-nginx-site.sh tenant1.vrugle.com [port] [email]
# Prereq: DNS A/AAAA record for the domain already points at this server.
# Same flow as your 1httpconfig / 2certbot / 3https files, in one idempotent script.
set -euo pipefail

DOMAIN=${1:?usage: sudo ./host-nginx-site.sh <domain> [port] [email]}
PORT=${2:-8099}                       # HTTP_PORT of the docker compose stack
EMAIL=${3:-contact@vrugle.com}
CONF=/etc/nginx/sites-available/$DOMAIN

[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
mkdir -p /var/www/certbot

# 1) HTTP vhost: ACME challenge + redirect (skipped if it already exists)
if [ ! -f "$CONF" ]; then
cat > "$CONF" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOF
ln -sf "$CONF" /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
fi

# 2) Certificate
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" \
    --cert-name "$DOMAIN" --email "$EMAIL" --agree-tos --no-eff-email --non-interactive
fi

# 3) HTTPS vhost -> docker stack. Host header MUST be passed through: Frappe
#    picks the tenant (site) from it.
if ! grep -q "listen 443" "$CONF"; then
cat >> "$CONF" <<EOF

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
EOF
fi

nginx -t && systemctl reload nginx
echo "Done: https://$DOMAIN  ->  127.0.0.1:$PORT"
