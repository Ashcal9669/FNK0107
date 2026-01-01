#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CODE_DIR="${REPO_DIR}/Code"
VENV_DIR="${CODE_DIR}/.venv"
SERVICE_NAME="freenove-case-pro"
DEFAULTS_FILE="/etc/default/${SERVICE_NAME}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run with sudo: sudo ${0}"
  exit 1
fi

if [[ ! -d "${CODE_DIR}" ]]; then
  echo "Code directory not found: ${CODE_DIR}"
  exit 1
fi

echo "Installing system packages..."
apt-get update
apt-get install -y python3 python3-venv python3-pip i2c-tools

echo "Setting up Python virtual environment..."
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${CODE_DIR}/requirements-headless.txt"

chmod +x "${CODE_DIR}/run_app.sh" "${CODE_DIR}/web_server.py"

if command -v modprobe >/dev/null 2>&1; then
  modprobe i2c-dev || true
fi

if [[ ! -e /dev/i2c-1 && ! -e /dev/i2c-0 ]]; then
  echo "Warning: /dev/i2c-* not found."
  echo "Enable I2C using raspi-config or add 'dtparam=i2c_arm=on' to /boot/firmware/config.txt, then reboot."
fi

if [[ ! -f "${DEFAULTS_FILE}" ]]; then
  cat > "${DEFAULTS_FILE}" <<'EOF'
FREENOVE_HOST=0.0.0.0
FREENOVE_PORT=8080
# FREENOVE_I2C_BUS=1
# FREENOVE_I2C_ADDR=0x21
EOF
fi

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Freenove Case Pro Headless UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${CODE_DIR}
EnvironmentFile=-${DEFAULTS_FILE}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python ${CODE_DIR}/web_server.py
Restart=on-failure
RestartSec=2
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"

echo "Service installed: ${SERVICE_NAME}"
echo "Open http://<pi-ip>:8080 from another device on the same network."
