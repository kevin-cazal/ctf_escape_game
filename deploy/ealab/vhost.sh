#!/bin/bash
# Usage: eg-vhost.sh <host> <port> http|https
set -euo pipefail
host=$1; port=$2; mode=$3
f=/etc/nginx/sites-available/$host.conf
{
cat <<CONF
# CTF escape game ($host) -> 127.0.0.1:$port. Written by hand for the POC, see
# ctf_escape_game/deploy/ealab. Certificates: certbot certonly --webroot.
server {
    listen 80;
    listen [::]:80;
    server_name $host;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}
CONF
if [ "$mode" = https ]; then
cat <<CONF

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $host;

    ssl_certificate     /etc/letsencrypt/live/$host/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$host/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=15768000" always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy same-origin always;
    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:$port;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect  off;
        proxy_buffering off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
    }
}
CONF
fi
} > $f
ln -sf $f /etc/nginx/sites-enabled/$host.conf
