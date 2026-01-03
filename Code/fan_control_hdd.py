import os
import time
import subprocess

PWM_BASE = os.environ.get("FREENOVE_HDD_PWM_BASE", "/sys/class/pwm/pwmchip0")
PWM_CHAN = os.path.join(PWM_BASE, "pwm0")
PERIOD = int(os.environ.get("FREENOVE_HDD_PWM_PERIOD", "40000"))
DRIVES_ENV = os.environ.get("FREENOVE_HDD_DRIVES", "/dev/sda,/dev/sdb")
DRIVES = [d.strip() for d in DRIVES_ENV.split(",") if d.strip()]

TEMP_DEFAULT = int(os.environ.get("FREENOVE_HDD_DEFAULT_TEMP", "25"))
POLL_INTERVAL = int(os.environ.get("FREENOVE_HDD_POLL_SECONDS", "30"))


def get_max_hdd_temp():
    temps = []
    for drive in DRIVES:
        try:
            output = subprocess.check_output(
                ["sudo", "smartctl", "-A", "-n", "standby", drive],
                text=True,
            )
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
