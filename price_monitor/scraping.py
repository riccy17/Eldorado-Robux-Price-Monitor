"""Playwright scraping helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import asyncio
import re

from .config import DEBUG_HTML_PATH, DEBUG_SCREENSHOT_PATH


@dataclass(slots=True)
class VendorOffer:
    rank: int
    vendor_name: str
    current_offer: float | None = None
    in_stock: str = "Check page"
    min_qty: str = "Check page"
    delivery_info: str = "Check page"

    def min_qty_value(self) -> int | None:
        digits = re.sub(r"[^\d]", "", str(self.min_qty))
        return int(digits) if digits else None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    return " ".join(text.split())


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.,]", "", text)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text)
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _format_int(value: int | None, fallback: str = "Check page") -> str:
    if value is None:
        return fallback
    return f"{value:,}"


async def _write_debug_artifacts(page) -> None:
    html_content = await page.content()
    DEBUG_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEBUG_HTML_PATH.open("w", encoding="utf-8") as handle:
        handle.write(html_content)
    await page.screenshot(path=str(DEBUG_SCREENSHOT_PATH), full_page=True)
    print(f"Saved debug HTML to {DEBUG_HTML_PATH}")
    print(f"Saved debug screenshot to {DEBUG_SCREENSHOT_PATH}")


async def scrape_vendors(page, num_vendors: int, debug: bool = False) -> list[VendorOffer]:
    vendors: list[VendorOffer] = []
    seen_names: set[str] = set()

    print("Waiting for page content to settle...")
    await page.wait_for_load_state("networkidle", timeout=20000)
    await asyncio.sleep(2)

    try:
        await page.wait_for_selector("#top-offer, .offer-seller-card", timeout=15000)
    except Exception:
        pass

    if debug:
        await _write_debug_artifacts(page)

    top_offer = await page.query_selector("#top-offer")
    if top_offer:
        vendor_name = None
        current_offer = None
        delivery_info = "Check page"
        in_stock = "Check page"
        min_qty = "Check page"

        name_element = await top_offer.query_selector(".profile__username a")
        if name_element:
            vendor_name = _clean_text(await name_element.inner_text())

        price_element = await top_offer.query_selector('strong[aria-label="amount-price"]')
        if price_element:
            current_offer = _parse_price(await price_element.inner_text())

        delivery_element = await top_offer.query_selector("eld-offer-details-combined-delivery-time")
        if delivery_element:
            delivery_info = _clean_text(await delivery_element.inner_text()) or "Check page"

        min_qty_element = await page.query_selector("eld-buy-now-card-desktop .min-quantity")
        stock_element = await page.query_selector("eld-buy-now-card-desktop .quantity")
        if not min_qty_element:
            min_qty_element = await page.query_selector("eld-buy-now-card-mobile .min-quantity")
        if not stock_element:
            stock_element = await page.query_selector("eld-buy-now-card-mobile .quantity")

        if min_qty_element:
            min_qty = _format_int(_parse_int(await min_qty_element.inner_text()))
        if stock_element:
            in_stock = _format_int(_parse_int(await stock_element.inner_text()))

        if vendor_name or current_offer is not None:
            fallback_name = vendor_name or f"Vendor {len(vendors) + 1}"
            vendors.append(
                VendorOffer(
                    rank=len(vendors) + 1,
                    vendor_name=fallback_name,
                    current_offer=current_offer,
                    in_stock=in_stock,
                    min_qty=min_qty,
                    delivery_info=delivery_info,
                )
            )
            seen_names.add(fallback_name)

    offer_cards = await page.query_selector_all(".offer-seller-card")
    for card in offer_cards:
        if len(vendors) >= num_vendors:
            break

        vendor_name = None
        current_offer = None
        in_stock = "Check page"
        min_qty = "Check page"
        delivery_info = "Check page"

        name_element = await card.query_selector(".profile__username a")
        if name_element:
            vendor_name = _clean_text(await name_element.inner_text())

        if vendor_name and vendor_name in seen_names:
            continue

        price_element = await card.query_selector('strong[aria-label="amount-price"]')
        if price_element:
            current_offer = _parse_price(await price_element.inner_text())

        detail_rows = await card.query_selector_all(".detail")
        for detail in detail_rows:
            label_element = await detail.query_selector(".label")
            value_element = await detail.query_selector(".value")
            if not label_element or not value_element:
                continue

            label = (_clean_text(await label_element.inner_text()) or "").lower()
            value_text = _clean_text(await value_element.inner_text()) or "Check page"

            if "in stock" in label:
                in_stock = _format_int(_parse_int(value_text), fallback=value_text)
            elif "min" in label:
                min_qty = _format_int(_parse_int(value_text), fallback=value_text)
            elif "delivery" in label:
                delivery_info = value_text

        fallback_name = vendor_name or f"Vendor {len(vendors) + 1}"
        vendors.append(
            VendorOffer(
                rank=len(vendors) + 1,
                vendor_name=fallback_name,
                current_offer=current_offer,
                in_stock=in_stock,
                min_qty=min_qty,
                delivery_info=delivery_info,
            )
        )
        seen_names.add(fallback_name)

    for vendor in vendors[:num_vendors]:
        if vendor.current_offer is not None:
            print(f"Extracted {vendor.vendor_name}: ${vendor.current_offer:.5f}")
        else:
            print(f"Extracted {vendor.vendor_name}: price not found")

    return vendors[:num_vendors]
