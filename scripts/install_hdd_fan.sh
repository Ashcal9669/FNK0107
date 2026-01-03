#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="/boot/firmware/config.txt"
SERVICE_SRC="$ROOT_DIR/scripts/freenove-hdd-fan.service"
SERVICE_DST="/etc/systemd/system/freenove-hdd-fan.service"
ENV_SRC="$ROOT_DIR/scripts/freenove-hdd-fan.conf.example"
ENV_DST="/etc/freenove-hdd-fan.conf"
ENV_DIR="/etc/freenove-hdd-fan.conf.d"
ENV_OVERRIDE="$ENV_DIR/override.conf"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

if ! command -v smartctl >/dev/null 2>&1; then
  echo "Installing smartmontools..."
  apt update
  apt install -y smartmontools
fi

if ! grep -q "^dtoverlay=pwm,pin=12,func=4" "$CONFIG_FILE"; then
  echo "Enabling PWM overlay in $CONFIG_FILE"
  echo "dtoverlay=pwm,pin=12,func=4" >> "$CONFIG_FILE"
  echo "PWM overlay added. Reboot required for PWM sysfs to appear."
fi

install -m 0644 "$SERVICE_SRC" "$SERVICE_DST"
if [[ ! -f "$ENV_DST" ]]; then
  install -m 0644 "$ENV_SRC" "$ENV_DST"
fi
mkdir -p "$ENV_DIR"
if [[ ! -f "$ENV_OVERRIDE" ]]; then
  cat <<'EOF' > "$ENV_OVERRIDE"
# Override defaults here. Example:
# FREENOVE_HDD_DRIVES=auto
# FREENOVE_HDD_EXCLUDE=/dev/sda
EOF
fi

systemctl daemon-reload
systemctl enable freenove-hdd-fan.service

cat <<EOF
Installed freenove-hdd-fan.service
- Edit $ENV_DST to set drives or polling interval.
- Optional overrides: $ENV_OVERRIDE
- Reboot if you just enabled the PWM overlay.
- Start service: sudo systemctl start freenove-hdd-fan
- Status: sudo systemctl status freenove-hdd-fan --no-pager
EOF
