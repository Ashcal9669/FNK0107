#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import threading
import time

from flask import Flask, jsonify, request, render_template

from api_expansion import Expansion
from api_json import ConfigManager
from api_systemInfo import SystemInformation

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "app_config.json")
WEB_DIR = os.path.join(APP_DIR, "web")
TEMPLATES_DIR = os.path.join(WEB_DIR, "templates")
STATIC_DIR = os.path.join(WEB_DIR, "static")

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)

config_lock = threading.Lock()
expansion_lock = threading.Lock()
process_lock = threading.Lock()

config_manager = ConfigManager(CONFIG_PATH)
system_info = SystemInformation()

expansion = None
processes = {
    "led": None,
    "fan": None,
    "oled": None,
}

PROCESS_SCRIPTS = {
    "led": "task_led.py",
    "fan": "task_fan.py",
    "oled": "task_oled.py",
}

FAN_TEMP_LIMITS = {
    "low": (10, 60),
    "high": (20, 80),
    "schmitt": (1, 5),
}


def clamp_int(value, min_value, max_value, default):
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, ivalue))


def scale_led_color(color, brightness):
    brightness = max(0, min(100, int(brightness)))
    scale = brightness / 100.0
    return [int(round(channel * scale)) for channel in color]


def map_pi_pwm_to_duty(pi_pwm, min_duty, max_duty):
    if pi_pwm is None or pi_pwm < 0:
        return None
    min_duty = max(0, min(255, int(min_duty)))
    max_duty = max(0, min(255, int(max_duty)))
    if max_duty < min_duty:
        min_duty, max_duty = max_duty, min_duty
    duty = min_duty + ((pi_pwm / 255.0) * (max_duty - min_duty))
    return max(0, min(255, int(round(duty))))


def get_config_value(section, key, default):
    value = config_manager.get_value(section, key)
    return default if value is None else value


def get_expansion():
    global expansion
    if expansion is None:
        expansion = Expansion()
    return expansion


def format_error(exc):
    message = str(exc).strip()
    return message.splitlines()[0] if message else "Unknown error"


def try_expansion():
    try:
        exp = get_expansion()
        return exp, None
    except Exception as exc:
        return None, format_error(exc)


def process_is_running(name):
    proc = processes.get(name)
    return proc is not None and proc.poll() is None


def set_process(name, enable):
    script = PROCESS_SCRIPTS.get(name)
    if not script:
        return False, f"Unknown process '{name}'"
    with process_lock:
        proc = processes.get(name)
        if enable:
            if proc is not None and proc.poll() is None:
                return True, "already running"
            script_path = os.path.join(APP_DIR, script)
            if not os.path.exists(script_path):
                return False, f"Missing script: {script_path}"
            processes[name] = subprocess.Popen([sys.executable, script_path], cwd=APP_DIR)
            return True, "started"
        if proc is None:
            return True, "already stopped"
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
        processes[name] = None
        return True, "stopped"


def read_config():
    with config_lock:
        config_manager.load_config()
        return config_manager.get_all_config()


def write_config(update_fn):
    with config_lock:
        config_manager.load_config()
        update_fn()
        config_manager.save_config()


def apply_led_mode(mode, color, brightness):
    scaled = scale_led_color(color, brightness)
    if mode == 0:
        return "rainbow", [("set_led_mode", 4)]
    if mode == 1:
        return "breathing", [("set_led_mode", 3), ("set_all_led_color", *scaled)]
    if mode == 2:
        return "follow", [("set_led_mode", 2), ("set_all_led_color", *scaled)]
    if mode == 3:
        return "manual", [("set_led_mode", 1), ("set_all_led_color", *scaled)]
    if mode == 5:
        return "off", [("set_led_mode", 0)]
    return "custom", []


def apply_fan_mode(mode, manual_duty, thresholds, speeds, pi_follow, pi_pwm):
    if mode == 0:
        return "follow_case", [
            ("set_fan_power_switch", 1),
            ("set_fan_frequency", 50000),
            ("set_fan_mode", 2),
            ("set_fan_threshold", *thresholds),
            ("set_fan_temp_mode_speed", *speeds),
        ]
    if mode == 1:
        mapped = map_pi_pwm_to_duty(pi_pwm, pi_follow[0], pi_follow[1])
        duty_value = mapped if mapped is not None else manual_duty[0]
        return "follow_pi", [
            ("set_fan_power_switch", 1),
            ("set_fan_frequency", 50000),
            ("set_fan_mode", 1),
            ("set_fan_duty", duty_value, duty_value, duty_value),
        ]
    if mode == 2:
        return "manual", [
            ("set_fan_power_switch", 1),
            ("set_fan_frequency", 50000),
            ("set_fan_mode", 1),
            ("set_fan_duty", *manual_duty),
        ]
    if mode == 4:
        return "off", [
            ("set_fan_mode", 0),
            ("set_fan_duty", 0, 0, 0),
            ("set_fan_power_switch", 0),
        ]
    return "custom", []


def set_save_flash(exp):
    try:
        exp.set_save_flash(1)
    except Exception:
        pass


def fan_follow_loop():
    last_duty = None
    while True:
        try:
            with config_lock:
                config_manager.load_config()
                mode = get_config_value("Fan", "mode", 0)
                follow = [
                    get_config_value("Fan", "mode3_min_speed_mapping", 0),
                    get_config_value("Fan", "mode3_max_speed_mapping", 255),
                ]
            if mode == 1 and not process_is_running("fan"):
                pi_pwm = system_info.get_raspberry_pi_fan_duty()
                duty = map_pi_pwm_to_duty(pi_pwm, follow[0], follow[1])
                if duty is not None and duty != last_duty:
                    exp, exp_err = try_expansion()
                    if not exp_err:
                        with expansion_lock:
                            exp.set_fan_power_switch(1)
                            exp.set_fan_frequency(50000)
                            exp.set_fan_mode(1)
                            exp.set_fan_duty(duty, duty, duty)
                        last_duty = duty
            else:
                last_duty = None
        except Exception:
            last_duty = None
        time.sleep(1.0)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def api_status():
    system = {
        "ip_address": system_info.get_raspberry_pi_ip_address(),
        "date": system_info.get_raspberry_pi_date(),
        "weekday": system_info.get_raspberry_pi_weekday(),
        "time": system_info.get_raspberry_pi_time(),
        "cpu_usage": system_info.get_raspberry_pi_cpu_usage(),
        "memory_usage": system_info.get_raspberry_pi_memory_usage(),
        "disk_usage": system_info.get_raspberry_pi_disk_usage(),
        "cpu_temp_c": system_info.get_raspberry_pi_cpu_temperature(),
        "rpi_fan_pwm": system_info.get_raspberry_pi_fan_duty(),
        "rpi_fan_mode": system_info.get_raspberry_pi_fan_mode(),
        "timestamp": time.time(),
    }

    expansion_info = {
        "case_temp_c": None,
        "fan_duty": [],
        "led_mode": None,
        "fan_mode": None,
        "error": None,
    }

    exp, exp_err = try_expansion()
    if exp_err:
        expansion_info["error"] = exp_err
    else:
        try:
            expansion_info["case_temp_c"] = exp.get_temp()
        except Exception as exc:
            expansion_info["error"] = str(exc)
        try:
            expansion_info["fan_duty"] = exp.get_fan_duty()
        except Exception:
            expansion_info["fan_duty"] = []
        try:
            expansion_info["led_mode"] = exp.get_led_mode()
        except Exception:
            expansion_info["led_mode"] = None
        try:
            expansion_info["fan_mode"] = exp.get_fan_mode()
        except Exception:
            expansion_info["fan_mode"] = None

    return jsonify(
        {
            "system": system,
            "expansion": expansion_info,
            "processes": {
                "led": process_is_running("led"),
                "fan": process_is_running("fan"),
                "oled": process_is_running("oled"),
            },
        }
    )


@app.get("/api/config")
def api_config():
    return jsonify(read_config())


@app.get("/api/processes")
def api_processes():
    limit = clamp_int(request.args.get("limit"), 1, 20, 6)
    return jsonify(
        {
            "timestamp": time.time(),
            "processes": system_info.get_top_processes(limit=limit),
        }
    )


@app.post("/api/led")
def api_led():
    payload = request.get_json(silent=True) or {}
    mode_raw = payload.get("mode")
    color = payload.get("color") or {}
    brightness_raw = payload.get("brightness")

    with config_lock:
        config_manager.load_config()
        current_mode = get_config_value("LED", "mode", 0)
        current_color = [
            get_config_value("LED", "red_value", 0),
            get_config_value("LED", "green_value", 0),
            get_config_value("LED", "blue_value", 255),
        ]
        current_brightness = get_config_value("LED", "brightness", 100)

        mode = clamp_int(mode_raw, 0, 5, current_mode) if mode_raw is not None else current_mode
        red = clamp_int(color.get("r"), 0, 255, current_color[0])
        green = clamp_int(color.get("g"), 0, 255, current_color[1])
        blue = clamp_int(color.get("b"), 0, 255, current_color[2])
        brightness = clamp_int(brightness_raw, 0, 100, current_brightness)

        config_manager.set_value("LED", "mode", mode)
        config_manager.set_value("LED", "red_value", red)
        config_manager.set_value("LED", "green_value", green)
        config_manager.set_value("LED", "blue_value", blue)
        config_manager.set_value("LED", "brightness", brightness)
        config_manager.save_config()

    if mode == 4:
        set_process("led", True)
    else:
        set_process("led", False)
        exp, exp_err = try_expansion()
        if exp_err:
            return jsonify({"ok": False, "error": exp_err}), 500
        _, calls = apply_led_mode(mode, [red, green, blue], brightness)
        with expansion_lock:
            for call in calls:
                method = getattr(exp, call[0])
                method(*call[1:])
            set_save_flash(exp)

    return jsonify({"ok": True})


@app.post("/api/fan")
def api_fan():
    payload = request.get_json(silent=True) or {}
    mode_raw = payload.get("mode")
    manual = payload.get("manual_duty") or []
    thresholds = payload.get("temp_threshold") or []
    speeds = payload.get("temp_speed") or []
    pi_follow = payload.get("pi_follow") or []

    with config_lock:
        config_manager.load_config()
        current_mode = get_config_value("Fan", "mode", 0)
        manual_defaults = [
            get_config_value("Fan", "mode1_fan_group1", 75),
            get_config_value("Fan", "mode1_fan_group2", 75),
            get_config_value("Fan", "mode1_fan_group3", 75),
        ]
        threshold_defaults = [
            get_config_value("Fan", "mode2_low_temp_threshold", 30),
            get_config_value("Fan", "mode2_high_temp_threshold", 50),
            get_config_value("Fan", "mode2_temp_schmitt", 3),
        ]
        speed_defaults = [
            get_config_value("Fan", "mode2_low_speed", 75),
            get_config_value("Fan", "mode2_middle_speed", 125),
            get_config_value("Fan", "mode2_high_speed", 175),
        ]
        follow_defaults = [
            get_config_value("Fan", "mode3_min_speed_mapping", 0),
            get_config_value("Fan", "mode3_max_speed_mapping", 255),
        ]

        mode = clamp_int(mode_raw, 0, 4, current_mode) if mode_raw is not None else current_mode
        duty = [
            clamp_int(manual[0] if len(manual) > 0 else None, 0, 255, manual_defaults[0]),
            clamp_int(manual[1] if len(manual) > 1 else None, 0, 255, manual_defaults[1]),
            clamp_int(manual[2] if len(manual) > 2 else None, 0, 255, manual_defaults[2]),
        ]
        thresh = [
            clamp_int(
                thresholds[0] if len(thresholds) > 0 else None,
                FAN_TEMP_LIMITS["low"][0],
                FAN_TEMP_LIMITS["low"][1],
                threshold_defaults[0],
            ),
            clamp_int(
                thresholds[1] if len(thresholds) > 1 else None,
                FAN_TEMP_LIMITS["high"][0],
                FAN_TEMP_LIMITS["high"][1],
                threshold_defaults[1],
            ),
            clamp_int(
                thresholds[2] if len(thresholds) > 2 else None,
                FAN_TEMP_LIMITS["schmitt"][0],
                FAN_TEMP_LIMITS["schmitt"][1],
                threshold_defaults[2],
            ),
        ]
        if thresh[1] <= thresh[0]:
            thresh[1] = min(FAN_TEMP_LIMITS["high"][1], thresh[0] + 1)
        speed = [
            clamp_int(speeds[0] if len(speeds) > 0 else None, 0, 255, speed_defaults[0]),
            clamp_int(speeds[1] if len(speeds) > 1 else None, 0, 255, speed_defaults[1]),
            clamp_int(speeds[2] if len(speeds) > 2 else None, 0, 255, speed_defaults[2]),
        ]
        follow = [
            clamp_int(pi_follow[0] if len(pi_follow) > 0 else None, 0, 255, follow_defaults[0]),
            clamp_int(pi_follow[1] if len(pi_follow) > 1 else None, 0, 255, follow_defaults[1]),
        ]

        config_manager.set_value("Fan", "mode", mode)
        config_manager.set_value("Fan", "mode1_fan_group1", duty[0])
        config_manager.set_value("Fan", "mode1_fan_group2", duty[1])
        config_manager.set_value("Fan", "mode1_fan_group3", duty[2])
        config_manager.set_value("Fan", "mode2_low_temp_threshold", thresh[0])
        config_manager.set_value("Fan", "mode2_high_temp_threshold", thresh[1])
        config_manager.set_value("Fan", "mode2_temp_schmitt", thresh[2])
        config_manager.set_value("Fan", "mode2_low_speed", speed[0])
        config_manager.set_value("Fan", "mode2_middle_speed", speed[1])
        config_manager.set_value("Fan", "mode2_high_speed", speed[2])
        config_manager.set_value("Fan", "mode3_min_speed_mapping", follow[0])
        config_manager.set_value("Fan", "mode3_max_speed_mapping", follow[1])
        config_manager.save_config()

    if mode == 3:
        set_process("fan", True)
    else:
        set_process("fan", False)
        exp, exp_err = try_expansion()
        if exp_err:
            return jsonify({"ok": False, "error": exp_err}), 500
        pi_pwm = system_info.get_raspberry_pi_fan_duty()
        _, calls = apply_fan_mode(mode, duty, thresh, speed, follow, pi_pwm)
        with expansion_lock:
            for call in calls:
                method = getattr(exp, call[0])
                method(*call[1:])
            set_save_flash(exp)

    return jsonify({"ok": True})


@app.post("/api/rpi-fan")
def api_rpi_fan():
    payload = request.get_json(silent=True) or {}
    enable_raw = payload.get("enable")
    pwm_raw = payload.get("pwm")

    with config_lock:
        config_manager.load_config()
        current_enable = bool(get_config_value("Fan", "rpi_manual_enable", False))
        current_pwm = get_config_value("Fan", "rpi_manual_pwm", 0)
        enable = current_enable if enable_raw is None else bool(enable_raw)
        pwm = clamp_int(pwm_raw, 0, 255, current_pwm)
        config_manager.set_value("Fan", "rpi_manual_enable", enable)
        config_manager.set_value("Fan", "rpi_manual_pwm", pwm)
        config_manager.save_config()

    if enable:
        ok = system_info.set_raspberry_pi_fan_duty(pwm)
        if not ok:
            return jsonify({"ok": False, "error": "Unable to set RPi fan PWM"}), 500
    else:
        system_info.set_raspberry_pi_fan_mode(2)

    return jsonify({"ok": True})


@app.post("/api/tasks")
def api_tasks():
    payload = request.get_json(silent=True) or {}
    led_on = payload.get("led")
    fan_on = payload.get("fan")
    oled_on = payload.get("oled")

    def update():
        if led_on is not None:
            config_manager.set_value("LED", "is_run_on_startup", bool(led_on))
        if fan_on is not None:
            config_manager.set_value("Fan", "is_run_on_startup", bool(fan_on))
        if oled_on is not None:
            config_manager.set_value("OLED", "is_run_on_startup", bool(oled_on))

    write_config(update)
    return jsonify({"ok": True})


@app.post("/api/process")
def api_process():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    enable = payload.get("enable")
    if name not in PROCESS_SCRIPTS:
        return jsonify({"ok": False, "error": "Unknown process"}), 400
    if enable is None:
        return jsonify({"ok": False, "error": "Missing enable flag"}), 400
    ok, message = set_process(name, bool(enable))
    status = 200 if ok else 500
    return jsonify({"ok": ok, "message": message, "running": process_is_running(name)}), status


def parse_args():
    parser = argparse.ArgumentParser(description="Freenove headless web UI")
    parser.add_argument("--host", default=os.environ.get("FREENOVE_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FREENOVE_PORT", "8080")))
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    threading.Thread(target=fan_follow_loop, daemon=True).start()
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
