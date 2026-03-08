"""Configuration and onboarding helpers for the price monitor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ALARM_DIR = ROOT_DIR / "alarm"
OUTPUT_DIR = ROOT_DIR / "output"
CONFIG_PATH = ROOT_DIR / "config.local.json"
RESULTS_PATH = OUTPUT_DIR / "price_check_results.json"
DEBUG_HTML_PATH = OUTPUT_DIR / "debug_page.html"
DEBUG_SCREENSHOT_PATH = OUTPUT_DIR / "debug_screenshot.png"

DEFAULT_TARGET_URL = "https://www.eldorado.gg/buy-robux/g/70-0-0?offerSortingCriterion=Cheapest"
DEFAULT_PRICE_THRESHOLD = 0.00380
DEFAULT_MAX_MIN_QTY = 2500
DEFAULT_INTERVAL_MINUTES = 3
DEFAULT_NUM_VENDORS = 5
DEFAULT_ALERT_VOLUME = 70
DEFAULT_SOUND_FILE = "boom.mp3"
SUPPORTED_AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav", ".wma"}


@dataclass(slots=True)
class TelegramConfig:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    timeout_seconds: int = 10

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> "TelegramConfig":
        payload = data or {}
        return cls(
            enabled=bool(payload.get("enabled", False)),
            bot_token=str(payload.get("bot_token", "") or ""),
            chat_id=str(payload.get("chat_id", "") or ""),
            timeout_seconds=int(payload["timeout_seconds"]) if "timeout_seconds" in payload else 10,
        )


@dataclass(slots=True)
class MonitorConfig:
    target_url: str = DEFAULT_TARGET_URL
    price_threshold: float = DEFAULT_PRICE_THRESHOLD
    max_min_qty: int = DEFAULT_MAX_MIN_QTY
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES
    num_vendors: int = DEFAULT_NUM_VENDORS
    sound_enabled: bool = True
    sound_file: str = DEFAULT_SOUND_FILE
    alert_volume: int = DEFAULT_ALERT_VOLUME
    telegram: TelegramConfig = field(default_factory=TelegramConfig)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MonitorConfig":
        return cls(
            target_url=str(data["target_url"]) if "target_url" in data else DEFAULT_TARGET_URL,
            price_threshold=float(data["price_threshold"]) if "price_threshold" in data else DEFAULT_PRICE_THRESHOLD,
            max_min_qty=int(data["max_min_qty"]) if "max_min_qty" in data else DEFAULT_MAX_MIN_QTY,
            interval_minutes=int(data["interval_minutes"]) if "interval_minutes" in data else DEFAULT_INTERVAL_MINUTES,
            num_vendors=int(data["num_vendors"]) if "num_vendors" in data else DEFAULT_NUM_VENDORS,
            sound_enabled=bool(data.get("sound_enabled", True)),
            sound_file=str(data["sound_file"]) if "sound_file" in data else DEFAULT_SOUND_FILE,
            alert_volume=int(data["alert_volume"]) if "alert_volume" in data else DEFAULT_ALERT_VOLUME,
            telegram=TelegramConfig.from_dict(data.get("telegram") if isinstance(data.get("telegram"), dict) else None),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def copy(self) -> "MonitorConfig":
        return MonitorConfig.from_dict(self.to_dict())


def ensure_runtime_dirs() -> None:
    ALARM_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def discover_alarm_files() -> list[Path]:
    ensure_runtime_dirs()
    alarm_files = [
        path
        for path in ALARM_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    ]
    return sorted(alarm_files, key=lambda path: (path.name.lower() != DEFAULT_SOUND_FILE, path.name.lower()))


def resolve_alarm_path(file_name: str) -> Path | None:
    for candidate in discover_alarm_files():
        if candidate.name == file_name:
            return candidate
    fallback = ALARM_DIR / DEFAULT_SOUND_FILE
    if fallback.exists():
        return fallback
    alarms = discover_alarm_files()
    return alarms[0] if alarms else None


def load_config(path: Path = CONFIG_PATH) -> MonitorConfig | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config payload in {path}")
    return MonitorConfig.from_dict(data)


def save_config(config: MonitorConfig, path: Path = CONFIG_PATH) -> None:
    ensure_runtime_dirs()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2)
        handle.write("\n")


def resolved_telegram_credentials(config: MonitorConfig) -> tuple[str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", config.telegram.bot_token).strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", config.telegram.chat_id).strip()
    return token, chat_id


def prompt_text(prompt: str, default: str | None = None, allow_empty: bool = False) -> str:
    while True:
        suffix = f" [{default}]" if default not in (None, "") else ""
        try:
            value = input(f"{prompt}{suffix}: ").strip()
        except EOFError:
            if default is not None:
                print()
                return default
            if allow_empty:
                print()
                return ""
            raise SystemExit("Setup cancelled: input stream ended before setup completed.")
        if value:
            return value
        if value == "" and default is not None:
            return default
        if allow_empty:
            return ""
        print("Please enter a value.")


def prompt_int(prompt: str, default: int, minimum: int = 0) -> int:
    while True:
        try:
            raw = input(f"{prompt} [{default}]: ").strip()
        except EOFError:
            print()
            return default
        if raw == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if value < minimum:
            print(f"Please enter a value >= {minimum}.")
            continue
        return value


def prompt_float(prompt: str, default: float, minimum: float = 0.0) -> float:
    while True:
        try:
            raw = input(f"{prompt} [{default:.5f}]: ").strip()
        except EOFError:
            print()
            return default
        if raw == "":
            return default
        try:
            value = float(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if value < minimum:
            print(f"Please enter a value >= {minimum}.")
            continue
        return value


def prompt_yes_no(prompt: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        try:
            raw = input(f"{prompt} [{suffix}]: ").strip().lower()
        except EOFError:
            print()
            return default
        if raw == "":
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please answer with y or n.")


def prompt_alarm_file(default_name: str) -> str:
    alarm_files = discover_alarm_files()
    if not alarm_files:
        print(f"No supported audio files were found in {ALARM_DIR}. Sound alerts will be disabled for now.")
        return ""

    if len(alarm_files) == 1:
        selected = alarm_files[0].name
        print(f"Using the only available alarm file: {selected}")
        return selected

    print(f"Available alarm files in {ALARM_DIR}:")
    for index, file_path in enumerate(alarm_files, start=1):
        marker = " (default)" if file_path.name == default_name else ""
        print(f"  {index}. {file_path.name}{marker}")

    default_index = 1
    for index, file_path in enumerate(alarm_files, start=1):
        if file_path.name == default_name:
            default_index = index
            break

    while True:
        try:
            raw = input(f"Choose an alarm file [{default_index}]: ").strip()
        except EOFError:
            print()
            return alarm_files[default_index - 1].name
        if raw == "":
            return alarm_files[default_index - 1].name
        try:
            selection = int(raw)
        except ValueError:
            print("Please enter a number from the list.")
            continue
        if 1 <= selection <= len(alarm_files):
            return alarm_files[selection - 1].name
        print("Please choose a valid number from the list.")


def prompt_secret(label: str, current_value: str, env_var_name: str) -> str:
    env_hint = f" or rely on {env_var_name}" if os.getenv(env_var_name) else ""
    if current_value:
        while True:
            try:
                raw = input(f"{label} (press Enter to keep the current saved value{env_hint}, '-' to clear): ").strip()
            except EOFError:
                print()
                return current_value
            if raw == "":
                return current_value
            if raw == "-":
                return ""
            return raw
    return prompt_text(f"{label} (leave blank to skip{env_hint})", allow_empty=True)


def run_onboarding(existing: MonitorConfig | None = None) -> MonitorConfig:
    ensure_runtime_dirs()
    config = existing.copy() if existing else MonitorConfig()

    print("=" * 72)
    print("ELDORADO.GG ROBUX PRICE MONITOR SETUP")
    print("=" * 72)
    print("This wizard stores your local settings in config.local.json.")
    print(f"Put custom alarm files in {ALARM_DIR}.")
    print()

    config.price_threshold = prompt_float("Alert when price is at or below", config.price_threshold, minimum=0.0)
    config.max_min_qty = prompt_int("Alert when min quantity is at or below", config.max_min_qty, minimum=1)
    config.interval_minutes = prompt_int("Monitor interval in minutes", config.interval_minutes, minimum=1)
    config.num_vendors = prompt_int("Number of vendors to inspect", config.num_vendors, minimum=1)
    config.alert_volume = prompt_int("Windows alert volume (0-100)", config.alert_volume, minimum=0)
    config.alert_volume = max(0, min(100, config.alert_volume))

    config.sound_enabled = prompt_yes_no("Enable sound alerts?", config.sound_enabled)
    if config.sound_enabled:
        selected_alarm = prompt_alarm_file(config.sound_file or DEFAULT_SOUND_FILE)
        if selected_alarm:
            config.sound_file = selected_alarm
        else:
            config.sound_enabled = False
            config.sound_file = ""
    else:
        config.sound_file = ""

    config.telegram.enabled = prompt_yes_no("Enable Telegram alerts?", config.telegram.enabled)
    if config.telegram.enabled:
        print("Telegram credentials are stored only in your local config or environment.")
        config.telegram.bot_token = prompt_secret(
            "Telegram bot token",
            config.telegram.bot_token,
            "TELEGRAM_BOT_TOKEN",
        )
        config.telegram.chat_id = prompt_secret(
            "Telegram chat ID",
            config.telegram.chat_id,
            "TELEGRAM_CHAT_ID",
        )
        token, chat_id = resolved_telegram_credentials(config)
        if not token or not chat_id:
            print("Telegram is enabled but incomplete. Alerts will be skipped until both values are configured.")
    else:
        config.telegram.bot_token = ""
        config.telegram.chat_id = ""

    print()
    print("Setup complete.")
    print(f"Local config will be saved to {CONFIG_PATH}.")
    print("=" * 72)
    return config
