#!/bin/bash
# One-command install of the relay as a service, from wherever this repo is cloned (Ubuntu/Debian or Oracle/RHEL).
#   git clone <repo> /opt/cudcampaign && sudo /opt/cudcampaign/kisak/relay/install-relay.sh
# Update later:  git -C /opt/cudcampaign pull && sudo systemctl restart cudcampaign-relay
# Options: PORT=28999 (env), --dry-run (print what it would do).
set -e
PORT="${PORT:-28999}"
DRY=""; [ "$1" = "--dry-run" ] && DRY=1
HERE="$(cd "$(dirname "$0")" && pwd)"
RELAY="$HERE/relay.py"
[ -f "$RELAY" ] || { echo "relay.py not found next to this script" >&2; exit 1; }
PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "python3 is not installed (apt install python3 / dnf install python3)" >&2; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' || { echo "python3 >= 3.8 needed" >&2; exit 1; }
run() { if [ -n "$DRY" ]; then echo "+ $*"; else "$@"; fi; }
case "$HERE" in /home/*|/root/*) echo "WARNING: $HERE is inside a home directory; the unprivileged service user cannot read it. Clone to /opt/cudcampaign instead." >&2; [ -n "$DRY" ] || exit 1;; esac
[ -n "$DRY" ] || [ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

UNIT=$(cat <<UNITEOF
[Unit]
Description=CudCampaign co-op relay
After=network.target

[Service]
User=cudrelay
ExecStart=$PY $RELAY --port $PORT
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6
RestrictNamespaces=true
LockPersonality=true
MemoryMax=256M
TasksMax=256
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
UNITEOF
)
echo "== service user"
id cudrelay >/dev/null 2>&1 || run useradd --system --no-create-home --shell /usr/sbin/nologin cudrelay
echo "== systemd unit (runs $RELAY on port $PORT)"
if [ -n "$DRY" ]; then echo "$UNIT"; else echo "$UNIT" > /etc/systemd/system/cudcampaign-relay.service; fi
run systemctl daemon-reload
run systemctl enable --now cudcampaign-relay
echo "== firewall on this machine (port $PORT/tcp)"
if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld 2>/dev/null; then
  run firewall-cmd --permanent --add-port=$PORT/tcp
  run firewall-cmd --reload
elif command -v iptables >/dev/null 2>&1; then
  if ! iptables -C INPUT -p tcp --dport $PORT -m state --state NEW -j ACCEPT 2>/dev/null; then
    # before the REJECT rule that Oracle's Ubuntu images end the chain with
    run iptables -I INPUT 1 -p tcp --dport $PORT -m state --state NEW -j ACCEPT
  fi
  if command -v netfilter-persistent >/dev/null 2>&1; then run netfilter-persistent save
  elif command -v apt-get >/dev/null 2>&1; then
    run env DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
    run netfilter-persistent save
  fi
else
  echo "no firewall tool found; nothing to open"
fi
echo
echo "Done. Still needed once, in the cloud console: allow TCP $PORT in the VCN security list (ingress, source 0.0.0.0/0)."
echo "Check:  systemctl status cudcampaign-relay      Test from another machine:  nc -vz <public-ip> $PORT"
