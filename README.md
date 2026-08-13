# FNK0107U, FNK0107V, FNK0107W - Freenove Computer Case Kit Pro for Raspberry Pi

Control UI + services for the FNK0107 case (Pi 5).

## Install (Pi)

Headless install on Debian/Ubuntu/Kali:

```bash
sudo git clone https://github.com/Ashcal9669/FNK0107.git /opt/FNK0107
cd /opt/FNK0107
sudo ./scripts/install_headless.sh
```

Open `http://<pi-ip>:8080` from another device on the same LAN.

## Update (Pi)

```bash
sudo git -C /opt/FNK0107 pull origin main
cd /opt/FNK0107
sudo ./scripts/install_headless.sh
```

## Manual Run (Headless)

```bash
cd /opt/FNK0107/Code
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-headless.txt
python3 web_server.py --host 0.0.0.0 --port 8080
```

## Notes

- If `/dev/i2c-*` is missing, enable I2C in `raspi-config` or add `dtparam=i2c_arm=on` to `/boot/firmware/config.txt`, then reboot.
- If I2C access is restricted, run with `sudo` or add your user to the `i2c` group.
- Set `FREENOVE_I2C_BUS` or `FREENOVE_I2C_ADDR` to override the default I2C bus or address.
- The web UI has no authentication; keep it on trusted networks.
