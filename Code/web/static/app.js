const $ = (id) => document.getElementById(id);
const qsa = (sel) => Array.from(document.querySelectorAll(sel));

let latestProcesses = { led: false, fan: false, oled: false };

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function setText(id, text) {
  const el = $(id);
  if (el) {
    el.textContent = text;
  }
}

function setMeter(id, percent) {
  const el = $(id);
  if (el) {
    el.style.width = `${clamp(percent, 0, 100)}%`;
  }
}

function showToast(message, isError = false) {
  const toast = $("toast");
  const text = message && message.length > 120 ? `${message.slice(0, 117)}...` : message;
  toast.textContent = text || "Request failed";
  toast.classList.remove("hidden");
  toast.style.background = isError ? "#7f1d1d" : "#1f2933";
  setTimeout(() => toast.classList.add("hidden"), 2200);
}

function rgbToHex(r, g, b) {
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  const num = parseInt(clean, 16);
  return {
    r: (num >> 16) & 255,
    g: (num >> 8) & 255,
    b: num & 255,
  };
}

function updateLedColorPreview(r, g, b) {
  $("led-color-preview").style.background = rgbToHex(r, g, b);
}

function syncLedSliders(r, g, b) {
  $("led-red").value = r;
  $("led-green").value = g;
  $("led-blue").value = b;
  $("led-red-value").textContent = r;
  $("led-green-value").textContent = g;
  $("led-blue-value").textContent = b;
  $("led-color-picker").value = rgbToHex(r, g, b);
  updateLedColorPreview(r, g, b);
}

function getSelectedValue(name) {
  const checked = document.querySelector(`input[name="${name}"]:checked`);
  return checked ? parseInt(checked.value, 10) : null;
}

function setSelectedValue(name, value) {
  const target = document.querySelector(`input[name="${name}"][value="${value}"]`);
  if (target) {
    target.checked = true;
  }
}

function setLedControlsEnabled(enabled) {
  ["led-color-picker", "led-red", "led-green", "led-blue"].forEach((id) => {
    $(id).disabled = !enabled;
  });
}

function toggleLedCustom(mode) {
  const show = mode === 4;
  $("led-custom-row").classList.toggle("hidden", !show);
  setLedControlsEnabled([1, 2, 3].includes(mode));
}

function toggleFanSections(mode) {
  $("fan-follow-case").classList.toggle("hidden", mode !== 0);
  $("fan-follow-pi").classList.toggle("hidden", mode !== 1);
  $("fan-manual").classList.toggle("hidden", mode !== 2);
  $("fan-custom-row").classList.toggle("hidden", mode !== 3);
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (err) {
      data = null;
    }
  }
  if (!response.ok) {
    const message = data && data.error ? data.error : (text || `Request failed: ${response.status}`);
    throw new Error(message);
  }
  return data ?? {};
}

async function loadConfig() {
  const config = await fetchJson("/api/config");
  const led = config.LED || {};
  const fan = config.Fan || {};
  const oled = config.OLED || {};

  setSelectedValue("led-mode", led.mode ?? 0);
  syncLedSliders(led.red_value ?? 0, led.green_value ?? 0, led.blue_value ?? 255);
  toggleLedCustom(led.mode ?? 0);

  setSelectedValue("fan-mode", fan.mode ?? 0);
  $("fan-low-temp").value = fan.mode2_low_temp_threshold ?? 30;
  $("fan-high-temp").value = fan.mode2_high_temp_threshold ?? 50;
  $("fan-schmitt").value = fan.mode2_temp_schmitt ?? 3;

  $("fan-low-speed").value = fan.mode2_low_speed ?? 75;
  $("fan-mid-speed").value = fan.mode2_middle_speed ?? 125;
  $("fan-high-speed").value = fan.mode2_high_speed ?? 175;
  $("fan-low-speed-value").textContent = $("fan-low-speed").value;
  $("fan-mid-speed-value").textContent = $("fan-mid-speed").value;
  $("fan-high-speed-value").textContent = $("fan-high-speed").value;

  $("fan-pi-min").value = fan.mode3_min_speed_mapping ?? 0;
  $("fan-pi-max").value = fan.mode3_max_speed_mapping ?? 255;
  $("fan-pi-min-value").textContent = $("fan-pi-min").value;
  $("fan-pi-max-value").textContent = $("fan-pi-max").value;

  $("fan-duty-1").value = fan.mode1_fan_group1 ?? 75;
  $("fan-duty-2").value = fan.mode1_fan_group2 ?? 75;
  $("fan-duty-3").value = fan.mode1_fan_group3 ?? 75;
  $("fan-duty-1-value").textContent = $("fan-duty-1").value;
  $("fan-duty-2-value").textContent = $("fan-duty-2").value;
  $("fan-duty-3-value").textContent = $("fan-duty-3").value;

  toggleFanSections(fan.mode ?? 0);

  $("task-led").checked = !!led.is_run_on_startup;
  $("task-fan").checked = !!fan.is_run_on_startup;
  $("task-oled").checked = !!oled.is_run_on_startup;
}

function updateStatus(data) {
  const system = data.system || {};
  const expansion = data.expansion || {};
  latestProcesses = data.processes || latestProcesses;

  setText("ip-address", system.ip_address || "--");
  setText("system-date", system.date || "--");
  setText("system-time", system.time || "--");

  const cpu = parseFloat(system.cpu_usage || 0);
  setText("cpu-usage", `${cpu.toFixed(1)}%`);
  setMeter("cpu-usage-bar", cpu);

  const mem = Array.isArray(system.memory_usage) ? system.memory_usage : [system.memory_usage || 0];
  const memPercent = parseFloat(mem[0] || 0);
  setText("ram-usage", `${memPercent.toFixed(1)}%`);
  setMeter("ram-usage-bar", memPercent);

  const disk = Array.isArray(system.disk_usage) ? system.disk_usage : [system.disk_usage || 0];
  const diskPercent = parseFloat(disk[0] || 0);
  setText("disk-usage", `${diskPercent.toFixed(1)}%`);
  setMeter("disk-usage-bar", diskPercent);

  const cpuTemp = parseFloat(system.cpu_temp_c || 0);
  setText("cpu-temp", `${cpuTemp.toFixed(1)}C`);
  setMeter("cpu-temp-bar", clamp((cpuTemp / 80) * 100, 0, 100));

  const caseTemp = expansion.case_temp_c != null ? parseFloat(expansion.case_temp_c) : null;
  const caseTempText = caseTemp == null ? "--" : `${caseTemp.toFixed(1)}C`;
  setText("case-temp", caseTempText);
  setText("case-temp-card", caseTempText);
  setMeter("case-temp-bar", caseTemp == null ? 0 : clamp((caseTemp / 80) * 100, 0, 100));

  const rpiPwm = parseFloat(system.rpi_fan_pwm || 0);
  const rpiPercent = clamp((rpiPwm / 255) * 100, 0, 100);
  setText("rpi-pwm", `${rpiPercent.toFixed(1)}%`);
  setMeter("rpi-pwm-bar", rpiPercent);

  const fanDuty = Array.isArray(expansion.fan_duty) ? expansion.fan_duty : [];
  const pwm1 = fanDuty.length > 0 ? clamp((fanDuty[0] / 255) * 100, 0, 100) : 0;
  const pwm2 = fanDuty.length > 1 ? clamp((fanDuty[1] / 255) * 100, 0, 100) : 0;
  setText("case-pwm-1", fanDuty.length > 0 ? `${pwm1.toFixed(1)}%` : "--");
  setText("case-pwm-2", fanDuty.length > 1 ? `${pwm2.toFixed(1)}%` : "--");
  setMeter("case-pwm-1-bar", pwm1);
  setMeter("case-pwm-2-bar", pwm2);

  const expansionChip = $("expansion-status");
  if (expansion.error) {
    expansionChip.textContent = "Expansion: error";
    expansionChip.style.background = "rgba(244, 162, 97, 0.2)";
    expansionChip.style.color = "#9b5419";
    expansionChip.title = expansion.error;
  } else {
    expansionChip.textContent = "Expansion: ready";
    expansionChip.style.background = "rgba(42, 157, 143, 0.2)";
    expansionChip.style.color = "#1f5b54";
    expansionChip.title = "";
  }

  $("led-custom-toggle").textContent = latestProcesses.led ? "Stop" : "Start";
  $("fan-custom-toggle").textContent = latestProcesses.fan ? "Stop" : "Start";
  $("oled-toggle").textContent = latestProcesses.oled ? "Stop" : "Start";
}

async function refreshStatus() {
  try {
    const data = await fetchJson("/api/status");
    updateStatus(data);
  } catch (err) {
    showToast(err.message || "Status refresh failed", true);
  }
}

async function applyLed() {
  const mode = getSelectedValue("led-mode") ?? 0;
  const r = parseInt($("led-red").value, 10);
  const g = parseInt($("led-green").value, 10);
  const b = parseInt($("led-blue").value, 10);
  try {
    await fetchJson("/api/led", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, color: { r, g, b } }),
    });
    showToast("LED updated");
    toggleLedCustom(mode);
    refreshStatus();
  } catch (err) {
    showToast(err.message || "LED update failed", true);
  }
}

async function applyFan() {
  const mode = getSelectedValue("fan-mode") ?? 0;
  const payload = {
    mode,
    manual_duty: [
      parseInt($("fan-duty-1").value, 10),
      parseInt($("fan-duty-2").value, 10),
      parseInt($("fan-duty-3").value, 10),
    ],
    temp_threshold: [
      parseInt($("fan-low-temp").value, 10),
      parseInt($("fan-high-temp").value, 10),
      parseInt($("fan-schmitt").value, 10),
    ],
    temp_speed: [
      parseInt($("fan-low-speed").value, 10),
      parseInt($("fan-mid-speed").value, 10),
      parseInt($("fan-high-speed").value, 10),
    ],
    pi_follow: [
      parseInt($("fan-pi-min").value, 10),
      parseInt($("fan-pi-max").value, 10),
    ],
  };

  try {
    await fetchJson("/api/fan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showToast("Fan updated");
    toggleFanSections(mode);
    refreshStatus();
  } catch (err) {
    showToast(err.message || "Fan update failed", true);
  }
}

async function applyTasks() {
  const payload = {
    led: $("task-led").checked,
    fan: $("task-fan").checked,
    oled: $("task-oled").checked,
  };
  try {
    await fetchJson("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showToast("Tasks saved");
  } catch (err) {
    showToast(err.message || "Task update failed", true);
  }
}

async function toggleProcess(name) {
  const enable = !latestProcesses[name];
  try {
    const data = await fetchJson("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, enable }),
    });
    latestProcesses[name] = data.running;
    showToast(`${name.toUpperCase()} ${data.running ? "started" : "stopped"}`);
    refreshStatus();
  } catch (err) {
    showToast(err.message || `${name.toUpperCase()} action failed`, true);
  }
}

function setupListeners() {
  $("led-apply").addEventListener("click", applyLed);
  $("fan-apply").addEventListener("click", applyFan);
  $("tasks-apply").addEventListener("click", applyTasks);

  $("led-custom-toggle").addEventListener("click", () => toggleProcess("led"));
  $("fan-custom-toggle").addEventListener("click", () => toggleProcess("fan"));
  $("oled-toggle").addEventListener("click", () => toggleProcess("oled"));

  $("led-color-picker").addEventListener("input", (event) => {
    const rgb = hexToRgb(event.target.value);
    syncLedSliders(rgb.r, rgb.g, rgb.b);
  });

  ["led-red", "led-green", "led-blue"].forEach((id) => {
    $(id).addEventListener("input", () => {
      const r = parseInt($("led-red").value, 10);
      const g = parseInt($("led-green").value, 10);
      const b = parseInt($("led-blue").value, 10);
      syncLedSliders(r, g, b);
    });
  });

  qsa('input[name="led-mode"]').forEach((input) => {
    input.addEventListener("change", () => {
      const mode = parseInt(input.value, 10);
      toggleLedCustom(mode);
    });
  });

  qsa('input[name="fan-mode"]').forEach((input) => {
    input.addEventListener("change", () => {
      const mode = parseInt(input.value, 10);
      toggleFanSections(mode);
    });
  });

  [
    ["fan-low-speed", "fan-low-speed-value"],
    ["fan-mid-speed", "fan-mid-speed-value"],
    ["fan-high-speed", "fan-high-speed-value"],
    ["fan-pi-min", "fan-pi-min-value"],
    ["fan-pi-max", "fan-pi-max-value"],
    ["fan-duty-1", "fan-duty-1-value"],
    ["fan-duty-2", "fan-duty-2-value"],
    ["fan-duty-3", "fan-duty-3-value"],
  ].forEach(([sliderId, labelId]) => {
    $(sliderId).addEventListener("input", () => {
      $(labelId).textContent = $(sliderId).value;
    });
  });
}

async function init() {
  try {
    setupListeners();
    await loadConfig();
    await refreshStatus();
    setInterval(refreshStatus, 1000);
  } catch (err) {
    showToast(err.message || "Startup failed", true);
  }
}

init();
