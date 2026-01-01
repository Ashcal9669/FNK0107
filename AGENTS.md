# Repository Guidelines

## Project Structure & Module Organization
- `Code/` contains the Python app, hardware control modules (`api_*.py`, `task_*.py`), UI modules (`app_ui*.py`), and entry points.
- `Code/web/` holds the headless web UI (`templates/index.html`, `static/app.js`, `static/styles.css`).
- `Code/data/` stores sample media (for example, `Jingle Bells.mp3`).
- `Code/picture/` contains UI images and the GIF processing script.
- Documentation lives in `README.md` and PDFs in the repo root; datasheets are in `Datasheet/`, product photos in `Picture/`.

## Build, Test, and Development Commands
- `cd Code`
- `python3 -m venv .venv && source .venv/bin/activate` sets up a local virtual environment.
- `pip install -r requirements.txt` for the full UI on a Pi with a display; `pip install -r requirements-headless.txt` for the headless web UI.
- `sudo python3 app_ui.py` runs the on-device PyQt UI (requires display and hardware access).
- `python3 web_server.py --host 0.0.0.0 --port 8080` runs the headless web UI; `run_app.sh` auto-detects display vs headless mode.
- `FREENOVE_HOST`, `FREENOVE_PORT`, and `FREENOVE_USE_SUDO=1` are supported by `run_app.sh`.

## Coding Style & Naming Conventions
- Python 3 with 4-space indentation.
- Modules and functions use `snake_case` (for example, `api_systemInfo.py`, `load_ui_config`); classes use `CamelCase`.
- Keep hardware interactions in `api_*.py` and background tasks in `task_*.py`.
- No formatter or linter is enforced in this repo; match the existing style and comment usage.

## Testing Guidelines
- No automated test suite or coverage requirements are included.
- Validate changes manually on target hardware: launch `app_ui.py` for the screen UI, and `web_server.py` for headless UI; verify sensors, fan/LED controls, and OLED behavior.

## Commit & Pull Request Guidelines
- Commit history uses short imperative messages like `Update README.md`, `Upload tutorial`, and `Revert "Update tutorial"`.
- Keep commits focused and descriptive; prefer one change set per commit.
- For PRs, include a concise summary, test steps, and screenshots or GIFs for UI changes (Qt or web).

## Security & Configuration Tips
- The headless web UI has no authentication; use trusted networks only.
- I2C access may require `sudo` or adding the user to the `i2c` group.
- If deploying on Raspberry Pi, document OS version and hardware configuration (SSD slots, display).
