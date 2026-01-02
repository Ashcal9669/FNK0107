import os
import sys
import time
import psutil
import atexit
import signal
import threading
import datetime
import socket

class SystemInformation:

    def __init__(self):
        self._rpi_fan_pwm_path = None
        self._rpi_fan_pwm_enable_path = None

    def _resolve_raspberry_pi_fan_paths(self):
        if self._rpi_fan_pwm_path and os.path.exists(self._rpi_fan_pwm_path):
            return self._rpi_fan_pwm_path, self._rpi_fan_pwm_enable_path

        base_paths = [
            "/sys/devices/platform/cooling_fan/hwmon",
            "/sys/class/hwmon",
        ]
        for base_path in base_paths:
            if not os.path.isdir(base_path):
                continue
            for entry in os.listdir(base_path):
                if not entry.startswith("hwmon"):
                    continue
                pwm_path = os.path.join(base_path, entry, "pwm1")
                if not os.path.exists(pwm_path):
                    continue
                enable_path = os.path.join(base_path, entry, "pwm1_enable")
                self._rpi_fan_pwm_path = pwm_path
                self._rpi_fan_pwm_enable_path = enable_path if os.path.exists(enable_path) else None
                return self._rpi_fan_pwm_path, self._rpi_fan_pwm_enable_path

        self._rpi_fan_pwm_path = None
        self._rpi_fan_pwm_enable_path = None
        return None, None

    def get_raspberry_pi_ip_address(self):
        """Get the IP address of the Raspberry Pi"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            return ip_address
        except Exception:
            return "0.0.0.0"

    def get_raspberry_pi_date(self):
        """Get the current date in YYYY-MM-DD format using native Python datetime"""
        try:
            return datetime.date.today().strftime('%Y-%m-%d')
        except Exception:
            return "1990-1-1"

    def get_raspberry_pi_weekday(self):
        """Get the current weekday name using native Python datetime"""
        try:
            return datetime.date.today().strftime('%A')
        except Exception:
            return "Error"

    def get_raspberry_pi_time(self):
        """Get the current time in HH:MM:SS format using native Python datetime"""
        try:
            return datetime.datetime.now().strftime('%H:%M:%S')
        except Exception:
            return '0:0:0'

    def get_raspberry_pi_cpu_usage(self):
        """Get the CPU usage percentage"""
        try:
            return psutil.cpu_percent(interval=0)
        except Exception:
            return 0

    def get_raspberry_pi_memory_usage(self):
        """Get the memory usage percentage"""
        try:
            memory = psutil.virtual_memory()
            return [memory.percent,round(memory.used//1024//1024/1024,3),round(memory.total//1024//1024/1024,3)]
        except Exception:
            return 0

    def get_raspberry_pi_disk_usage(self, path='/'):
        """Get the disk usage percentage for all disk partitions"""
        try:
            total_used = 0
            total_size = 0
            
            # Get all disk partitions
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                try:
                    # Get partition usage information
                    usage = psutil.disk_usage(partition.mountpoint)
                    total_used += usage.used
                    total_size += usage.total
                except PermissionError:
                    # Some partitions may not have access permissions, skip
                    continue
                except Exception:
                    # Skip other exceptions
                    continue
            
            # If no partition information is found, return default values
            if total_size == 0:
                return [0, 0, 0]
            
            # Calculate total usage percentage
            total_percent = round((total_used / total_size) * 100, 2)
            
            # Convert to GB and round to appropriate decimal places
            used_gb = round(total_used / (1024**3), 3)
            total_gb = round(total_size / (1024**3), 3)
            
            return [total_percent, used_gb, total_gb]
        except Exception:
            return [0, 0, 0]

    def get_raspberry_pi_fan_duty(self, max_retries=3, retry_delay=0.1):
        """Get fan PWM using cached path and direct file read instead of subprocess"""
        for attempt in range(max_retries + 1):
            try:
                fan_input_path, _ = self._resolve_raspberry_pi_fan_paths()
                if not fan_input_path:
                    raise FileNotFoundError("No fan PWM path found")
                # Direct file read instead of subprocess
                with open(fan_input_path, 'r') as f:
                    pwm_value = int(f.read().strip())
                    return max(0, min(255, pwm_value))  # Clamp between 0-255
                    
            except (OSError, ValueError) as e:
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    return -1
            except Exception:
                return -1
        return -1

    def get_raspberry_pi_fan_mode(self):
        """Get the current fan control mode from pwm1_enable when available."""
        _, enable_path = self._resolve_raspberry_pi_fan_paths()
        if not enable_path:
            return None
        try:
            with open(enable_path, 'r') as f:
                return int(f.read().strip())
        except Exception:
            return None

    def set_raspberry_pi_fan_mode(self, mode):
        """Set the fan control mode using pwm1_enable if available."""
        _, enable_path = self._resolve_raspberry_pi_fan_paths()
        if not enable_path:
            return False
        try:
            with open(enable_path, 'w') as f:
                f.write(str(int(mode)))
            return True
        except Exception:
            return False

    def set_raspberry_pi_fan_duty(self, pwm_value):
        """Set fan PWM duty and switch to manual mode when possible."""
        fan_input_path, _ = self._resolve_raspberry_pi_fan_paths()
        if not fan_input_path:
            return False
        try:
            self.set_raspberry_pi_fan_mode(1)
            pwm_value = max(0, min(255, int(pwm_value)))
            with open(fan_input_path, 'w') as f:
                f.write(str(pwm_value))
            return True
        except Exception:
            return False

    def get_raspberry_pi_cpu_temperature(self):
        """Get the CPU temperature in Celsius using direct file read"""
        try:
            with open('/sys/devices/virtual/thermal/thermal_zone0/temp', 'r') as f:
                temp_raw = int(f.read().strip())
                return temp_raw / 1000.0
        except Exception:
            return 0

    def get_top_processes(self, limit=6):
        """Get top processes by CPU usage with memory usage."""
        processes = []
        try:
            for proc in psutil.process_iter(attrs=["pid", "name", "username"]):
                try:
                    cpu = proc.cpu_percent(interval=None)
                    mem = proc.memory_percent()
                    info = proc.info
                    processes.append({
                        "pid": info.get("pid"),
                        "name": info.get("name") or "unknown",
                        "user": info.get("username") or "unknown",
                        "cpu_percent": round(cpu, 1),
                        "memory_percent": round(mem, 1),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            processes.sort(key=lambda item: (item["cpu_percent"], item["memory_percent"]), reverse=True)
            return processes[:max(1, min(limit, 20))]
        except Exception:
            return []


if __name__ == "__main__":
    system_information = SystemInformation()
    print(system_information.get_raspberry_pi_ip_address())
    print(system_information.get_raspberry_pi_date())
    print(system_information.get_raspberry_pi_weekday())
    print(system_information.get_raspberry_pi_time())
    print(system_information.get_raspberry_pi_cpu_usage())
    print(system_information.get_raspberry_pi_memory_usage())
    print(system_information.get_raspberry_pi_disk_usage())
    print(system_information.get_raspberry_pi_fan_duty())
    print(system_information.get_raspberry_pi_cpu_temperature())
    
