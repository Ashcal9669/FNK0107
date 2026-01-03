import os
import time
import subprocess

CONFIG_FILE = "/etc/freenove-hdd-fan.conf"
CONFIG_DIR = "/etc/freenove-hdd-fan.conf.d"


def parse_drive_list(raw):
    return [d.strip() for d in (raw or "").split(",") if d.strip()]


def read_env_file(path):
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
    except Exception:
        return {}
    return data


def read_env_dir(path):
    data = {}
    try:
        entries = sorted(
            entry for entry in os.listdir(path) if entry.endswith(".conf")
        )
    except Exception:
        return {}
    for entry in entries:
        data.update(read_env_file(os.path.join(path, entry)))
    return data


def load_config():
    config = {}
    config.update(read_env_file(CONFIG_FILE))
    config.update(read_env_dir(CONFIG_DIR))
    for key, value in os.environ.items():
        if key.startswith("FREENOVE_HDD_"):
            config[key] = value
    return config


def detect_hdd_drives():
    try:
        output = subprocess.check_output(
            ["smartctl", "--scan-open"], text=True
        )
    except Exception:
        output = ""
    drives = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        device = line.split()[0]
        if device.startswith("/dev/sd"):
            drives.append(device)
    return sorted(set(drives))


CONFIG = load_config()
PWM_BASE = CONFIG.get("FREENOVE_HDD_PWM_BASE", "/sys/class/pwm/pwmchip0")
PWM_CHAN = os.path.join(PWM_BASE, "pwm0")
PERIOD = int(CONFIG.get("FREENOVE_HDD_PWM_PERIOD", "40000"))
TEMP_DEFAULT = int(CONFIG.get("FREENOVE_HDD_DEFAULT_TEMP", "25"))
POLL_INTERVAL = int(CONFIG.get("FREENOVE_HDD_POLL_SECONDS", "30"))

DRIVES_RAW = CONFIG.get("FREENOVE_HDD_DRIVES", "auto")
DRIVES = parse_drive_list(DRIVES_RAW)
if not DRIVES or DRIVES_RAW.lower() == "auto":
    DRIVES = detect_hdd_drives()
EXCLUDE = parse_drive_list(CONFIG.get("FREENOVE_HDD_EXCLUDE", ""))
if EXCLUDE:
    DRIVES = [drive for drive in DRIVES if drive not in EXCLUDE]


def get_max_hdd_temp():
    temps = []
    for drive in DRIVES:
        try:
            result = subprocess.run(
                ["sudo", "smartctl", "-A", "-n", "standby", drive],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            output = result.stdout
            for line in output.splitlines():
                if "Temperature_Celsius" in line or "Airflow_Temperature_Cel" in line:
                    temp = int(line.split()[9])
                    temps.append(temp)
        except Exception:
            continue
    return max(temps) if temps else TEMP_DEFAULT


def set_fan_speed(percent):
    duty = int((percent / 100) * PERIOD)
    with open(os.path.join(PWM_CHAN, "duty_cycle"), "w") as f:
        f.write(str(duty))


def calculate_fan_curve(temp):
    if temp < 28:
        return 25
    if temp < 31:
        return 50
    if temp < 33:
        return 75
    return 100


def setup_pwm():
    if not os.path.exists(PWM_CHAN):
        with open(os.path.join(PWM_BASE, "export"), "w") as f:
            f.write("0")
        time.sleep(0.5)
    with open(os.path.join(PWM_CHAN, "period"), "w") as f:
        f.write(str(PERIOD))
    with open(os.path.join(PWM_CHAN, "enable"), "w") as f:
        f.write("1")


def main():
    setup_pwm()
    print("NAS HDD Control Started (Monitoring: {})".format(", ".join(DRIVES)))
    try:
        while True:
            max_temp = get_max_hdd_temp()
            speed = calculate_fan_curve(max_temp)
            set_fan_speed(speed)
            print(
                "Max HDD Temp: {}C | Target Fan Speed: {}%".format(max_temp, speed),
                end="\r",
            )
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopping... Setting fans to 25% for safety.")
        set_fan_speed(25)


if __name__ == "__main__":
    main()
