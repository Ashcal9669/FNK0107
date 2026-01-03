# FNK0107

Control UI + services for the FNK0107 case (Pi 5).

## Install (Pi)

Headless install on Debian/Ubuntu:

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

## Optional: HDD PWM Fan Control (Arctic Fan Hub)

This is optional and only for users with the following setup:

Structure:
- (1) Arctic Fan Hub
- (1) Raspberry Pi 5 (16GB)
- GPIO:
  - PIN 32 = PWM
  - PIN 34 = GND
  - PIN 38 = TKG (tachometer)
- (1) SATA cable (Arctic Fan Hub power source, must be 12V)
- (3) Separate cables: PWM, GND, TKG/tachometer

WARNING!
- Make sure the wiring is correct to avoid damaging the PMIC or SoC.
- Use a multimeter to verify lines.
- Power off both devices before wiring.

Install:
```bash
sudo ./scripts/install_hdd_fan.sh
```

Edit optional config:
```bash
sudo nano /etc/freenove-hdd-fan.conf
```

Start/stop:
```bash
sudo systemctl start freenove-hdd-fan
sudo systemctl stop freenove-hdd-fan
sudo systemctl status freenove-hdd-fan --no-pager
```

Notes:
- The script uses `smartctl` to read HDD temps and maps them to a fan curve.
- Defaults monitor `auto` (scan `/dev/sd*`) every 30 seconds with the built-in curve.
- Other users can edit `/etc/freenove-hdd-fan.conf` or add overrides in `/etc/freenove-hdd-fan.conf.d/override.conf` to change drive list, exclude drives, polling interval, and PWM period.
- The PWM overlay is added to `/boot/firmware/config.txt`:
  - `dtoverlay=pwm,pin=12,func=4`
- Reboot after enabling the overlay.
