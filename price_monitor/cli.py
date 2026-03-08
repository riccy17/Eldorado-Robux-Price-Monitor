"""Command-line interface for the price monitor."""

from __future__ import annotations

import argparse
import asyncio
import json

from .alerts import play_alert_sound
from .config import (
    ALARM_DIR,
    CONFIG_PATH,
    DEFAULT_ALERT_VOLUME,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_MAX_MIN_QTY,
    DEFAULT_NUM_VENDORS,
    DEFAULT_PRICE_THRESHOLD,
    MonitorConfig,
    ensure_runtime_dirs,
    load_config,
    resolved_telegram_credentials,
    run_onboarding,
    save_config,
)
from .runner import check_prices, monitor_continuous


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def volume_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0 or parsed > 100:
        raise argparse.ArgumentTypeError("volume must be between 0 and 100")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Eldorado.gg Robux Price Monitor")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--once", action="store_true", help="Run a single check and exit")
    mode_group.add_argument("--monitor", action="store_true", help="Run continuous monitoring (default)")
    parser.add_argument("--setup", action="store_true", help="Create or update the local config file")
    parser.add_argument(
        "--interval",
        type=positive_int,
        help=f"Monitor interval in minutes (default: {DEFAULT_INTERVAL_MINUTES})",
    )
    parser.add_argument(
        "--max-min-qty",
        type=positive_int,
        help=f"Max allowed min quantity for alerts (default: {DEFAULT_MAX_MIN_QTY})",
    )
    parser.add_argument(
        "--volume",
        type=volume_int,
        help=f"Windows alert volume 0-100 (default: {DEFAULT_ALERT_VOLUME})",
    )
    parser.add_argument("--sound-debug", action="store_true", help="Print Windows sound playback debug output")
    parser.add_argument("--sound-test", action="store_true", help="Play the configured alert sound and exit")
    parser.add_argument("--show-browser", action="store_true", help="Show the browser window")
    parser.add_argument(
        "--vendors",
        type=positive_int,
        help=f"Number of vendors to inspect (default: {DEFAULT_NUM_VENDORS})",
    )
    parser.add_argument(
        "--threshold",
        type=non_negative_float,
        help=f"Price threshold (default: {DEFAULT_PRICE_THRESHOLD:.5f})",
    )
    parser.add_argument("--debug", action="store_true", help="Save debug HTML and a screenshot in output/")
    return parser


def apply_cli_overrides(config: MonitorConfig, args: argparse.Namespace) -> MonitorConfig:
    runtime_config = config.copy()
    if args.threshold is not None:
        runtime_config.price_threshold = args.threshold
    if args.max_min_qty is not None:
        runtime_config.max_min_qty = args.max_min_qty
    if args.interval is not None:
        runtime_config.interval_minutes = args.interval
    if args.vendors is not None:
        runtime_config.num_vendors = args.vendors
    if args.volume is not None:
        runtime_config.alert_volume = max(0, min(100, args.volume))
    return runtime_config


def print_startup_summary(config: MonitorConfig, debug: bool, show_browser: bool) -> None:
    token, chat_id = resolved_telegram_credentials(config)
    telegram_status = "enabled" if config.telegram.enabled and token and chat_id else "disabled or incomplete"
    sound_status = config.sound_file if config.sound_enabled and config.sound_file else "disabled"

    print("=" * 80)
    print("ELDORADO.GG ROBUX PRICE MONITOR")
    print("=" * 80)
    print(f"Target URL: {config.target_url}")
    print(f"Price threshold: <= ${config.price_threshold:.5f}")
    print(f"Max min quantity: <= {config.max_min_qty}")
    print(f"Vendor limit: {config.num_vendors}")
    print(f"Monitor interval: {config.interval_minutes} minute(s)")
    print(f"Alarm directory: {ALARM_DIR}")
    print(f"Selected alarm: {sound_status}")
    print(f"Telegram: {telegram_status}")
    print(f"Browser mode: {'visible' if show_browser or debug else 'headless'}")
    if debug:
        print("Debug capture: enabled")
    print("=" * 80)
    print()


def load_or_create_config(force_setup: bool) -> tuple[MonitorConfig, bool]:
    config = None
    needs_setup = force_setup

    try:
        config = load_config()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Config load failed: {exc}")
        print("The setup wizard will recreate your local config.")
        needs_setup = True

    if config is None:
        needs_setup = True

    if needs_setup:
        config = run_onboarding(config)
        save_config(config)
        print(f"Saved local config to {CONFIG_PATH}")
        print()

    return config, needs_setup


def main() -> int:
    ensure_runtime_dirs()
    parser = build_parser()
    args = parser.parse_args()

    config, _ = load_or_create_config(force_setup=args.setup)

    if args.setup and not (args.once or args.monitor or args.sound_test):
        print("Setup complete. Run `python scraper.py --once` for a single check or `python scraper.py` to monitor.")
        return 0

    runtime_config = apply_cli_overrides(config, args)
    print_startup_summary(runtime_config, debug=args.debug, show_browser=args.show_browser)

    if args.sound_test:
        play_alert_sound(runtime_config, sound_debug=args.sound_debug)
        return 0

    headless = not args.show_browser and not args.debug

    try:
        if args.once:
            asyncio.run(check_prices(runtime_config, headless=headless, debug=args.debug))
        else:
            asyncio.run(monitor_continuous(runtime_config, headless=headless, debug=args.debug))
    except KeyboardInterrupt:
        print("Stopped by user.")
        return 130

    return 0
