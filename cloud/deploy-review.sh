#!/bin/bash
set -eu
REVIEW_HOST="$1"
cd /tmp
grep 'caddy_2.10.2_linux_amd64.tar.gz$' checksums.txt | sha512sum -c -
tar xzf caddy.tar.gz caddy
install -m 755 caddy /usr/local/bin/caddy
id alhidaya >/dev/null 2>&1 || useradd --system --home /var/lib/alhidaya --create-home alhidaya
chown -R alhidaya:alhidaya /opt/alhidaya /var/lib/alhidaya
chmod 600 /opt/alhidaya/bootstrap.json
cat > /etc/systemd/system/alhidaya.service <<EOF
[Unit]
Description=Al Hidaya temporary review app
After=network-online.target
[Service]
User=alhidaya
WorkingDirectory=/opt/alhidaya
ExecStart=/usr/bin/python3 /opt/alhidaya/cloud/server.py --data-dir /var/lib/alhidaya/data --origin https://$REVIEW_HOST --bootstrap /opt/alhidaya/bootstrap.json --demo
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/alhidaya /opt/alhidaya
[Install]
WantedBy=multi-user.target
EOF
mkdir -p /etc/caddy
cat > /etc/caddy/Caddyfile <<EOF
{
 admin off
}
$REVIEW_HOST {
 encode gzip
 reverse_proxy 127.0.0.1:8767
}
EOF
cat > /etc/systemd/system/caddy.service <<'EOF'
[Unit]
Description=HTTPS for temporary Al Hidaya review
After=network-online.target
[Service]
User=alhidaya
Environment=HOME=/var/lib/alhidaya
ExecStart=/usr/local/bin/caddy run --config /etc/caddy/Caddyfile
Restart=on-failure
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now alhidaya caddy
