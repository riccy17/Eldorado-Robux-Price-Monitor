"""Runtime orchestration for scraping and alert evaluation."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json

from playwright.async_api import async_playwright

from .alerts import play_alert_sound, send_telegram_message
from .config import MonitorConfig, RESULTS_PATH, ensure_runtime_dirs
from .scraping import VendorOffer, scrape_vendors


def _save_results(config: MonitorConfig, vendors: list[VendorOffer], matched_alerts: list[dict[str, object]]) -> None:
    ensure_runtime_dirs()
    payload = {
        "timestamp": datetime.now().isoformat(),
        "target_url": config.target_url,
        "threshold": config.price_threshold,
        "max_min_qty": config.max_min_qty,
        "alert_triggered": bool(matched_alerts),
        "matches": matched_alerts,
        "vendors": [vendor.to_dict() for vendor in vendors],
    }
    with RESULTS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    print(f"Results saved to {RESULTS_PATH}")


def _collect_matches(config: MonitorConfig, vendors: list[VendorOffer]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for vendor in vendors:
        min_qty_value = vendor.min_qty_value()
        price_ok = vendor.current_offer is not None and vendor.current_offer <= config.price_threshold
        min_qty_ok = min_qty_value is not None and min_qty_value <= config.max_min_qty
        if price_ok and min_qty_ok:
            matches.append(
                {
                    "vendor": vendor.vendor_name,
                    "price": vendor.current_offer,
                    "min_qty": min_qty_value,
                    "in_stock": vendor.in_stock,
                    "delivery": vendor.delivery_info,
                }
            )
    return matches


def _print_report(config: MonitorConfig, vendors: list[VendorOffer], matched_alerts: list[dict[str, object]], debug: bool) -> None:
    print()
    print("=" * 80)
    print(f"ELDORADO.GG ROBUX PRICE CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print(f"Target URL: {config.target_url}")
    print(f"Threshold: <= ${config.price_threshold:.5f}")
    print(f"Max min quantity: <= {config.max_min_qty}")
    if debug:
        print("Debug capture: enabled")

    if not vendors:
        print()
        print("No vendors were found. The page structure may have changed.")
        if debug:
            print("Inspect the files in output/ for more detail.")
        else:
            print("Re-run with --debug to save HTML and a screenshot in output/.")
        print("=" * 80)
        return

    for vendor in vendors:
        price_display = f"${vendor.current_offer:.5f}" if vendor.current_offer is not None else "Not found"
        print()
        print(f"#{vendor.rank} - {vendor.vendor_name}")
        print(f"  Current offer: {price_display}")
        print(f"  In stock: {vendor.in_stock}")
        print(f"  Min qty: {vendor.min_qty}")
        print(f"  Delivery: {vendor.delivery_info}")

    print()
    print("=" * 80)
    if matched_alerts:
        print("PRICE ALERT TRIGGERED")
        print(f"Matched {len(matched_alerts)} vendor(s).")
    else:
        print("No offers met both the price and min quantity thresholds.")
    print("=" * 80)


def _build_telegram_message(config: MonitorConfig, matched_alerts: list[dict[str, object]]) -> str:
    lines = [
        "ALERT: price and min-qty thresholds met",
        f"Price <= ${config.price_threshold:.5f} | Min Qty <= {config.max_min_qty}",
        f"Target: {config.target_url}",
        f"Matches: {len(matched_alerts)}",
    ]
    for match in matched_alerts:
        lines.append(
            f"- {match['vendor']}: ${match['price']:.5f}, min {match['min_qty']}, stock {match['in_stock']}, delivery {match['delivery']}"
        )
    return "\n".join(lines)


async def check_prices(config: MonitorConfig, headless: bool = True, debug: bool = False) -> tuple[list[VendorOffer], bool]:
    async with async_playwright() as playwright:
        print("Launching browser...")
        browser = await playwright.chromium.launch(headless=headless)
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = await context.new_page()

            print(f"Navigating to {config.target_url}")
            await page.goto(config.target_url, wait_until="networkidle", timeout=30000)
            print("Scraping vendor data...")
            vendors = await scrape_vendors(page, config.num_vendors, debug=debug)
        finally:
            await browser.close()

    matched_alerts = _collect_matches(config, vendors)
    _print_report(config, vendors, matched_alerts, debug=debug)

    if matched_alerts:
        play_alert_sound(config)
        send_telegram_message(config, _build_telegram_message(config, matched_alerts))

    _save_results(config, vendors, matched_alerts)
    return vendors, bool(matched_alerts)


async def monitor_continuous(config: MonitorConfig, headless: bool = True, debug: bool = False) -> None:
    print(f"Starting continuous monitoring. Checking every {config.interval_minutes} minute(s).")
    print("Press Ctrl+C to stop.")
    while True:
        try:
            await check_prices(config, headless=headless, debug=debug)
            print(f"Next check in {config.interval_minutes} minute(s)...")
            await asyncio.sleep(config.interval_minutes * 60)
        except KeyboardInterrupt:
            print("Monitoring stopped by user.")
            break
        except Exception as exc:
            print(f"Monitoring error: {exc}")
            print(f"Retrying in {config.interval_minutes} minute(s)...")
            await asyncio.sleep(config.interval_minutes * 60)
