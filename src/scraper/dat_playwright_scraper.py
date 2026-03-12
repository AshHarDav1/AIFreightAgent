"""DAT scraper driven by Octo Browser + Playwright.

This scraper assumes:
- Octo Browser desktop app is running on the same host.
- We start a profile for automation using the local Octo API
  (http://host.docker.internal:58888/api/profiles/start) and get a ws_endpoint.

Two-phase flow:
- open_for_scraping(profile_uuid): Start Octo, connect Playwright, navigate to DAT
  search page. Keeps browser open so user can fill filters manually.
- scrape_and_store_from_open(max_loads): Scrape the currently visible loads and
  persist to DB. Does not close the browser.
- close_scrape_session(): Close the stored browser connection.
"""

from __future__ import annotations

import traceback
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, Page

from src.utils.logger import logger
from src.utils.config import config
from src.octo.client import OctoClient
from src.database.database import db
from src.database.models import Load, Broker, ScrapeLog

# Global session: (playwright_context, playwright, browser, page) when "opened"
_scrape_session: Optional[Dict[str, Any]] = None


@dataclass
class ScrapedLoad:
    load_id: str
    origin: str
    destination: str
    miles: Optional[int]
    rate: Optional[float]
    equipment_type: Optional[str]
    pickup_date: Optional[str]
    delivery_date: Optional[str]
    weight: Optional[float]
    commodity: Optional[str]
    broker_name: Optional[str]
    broker_email: Optional[str]
    broker_phone: Optional[str]
    dat_url: Optional[str]
    raw_data: dict


def is_scrape_session_open() -> bool:
    """Return True if a scrape session is currently open (browser ready for manual filters)."""
    global _scrape_session
    return _scrape_session is not None and _scrape_session.get("page") is not None


async def open_for_scraping(profile_uuid: str) -> bool:
    """Start Octo profile, connect Playwright, navigate to DAT search page.
    Keeps browser open. Returns True on success."""
    global _scrape_session

    if not profile_uuid:
        logger.error("open_for_scraping: profile_uuid is empty")
        return False

    # Close any existing session first
    await close_scrape_session()

    octo = OctoClient()
    ws_endpoint = await octo.start_profile_for_playwright(profile_uuid)
    if not ws_endpoint:
        logger.error("Octo did not return ws_endpoint")
        return False

    logger.info(f"Connecting to Octo CDP: {ws_endpoint}")

    pw = async_playwright()
    playwright = await pw.__aenter__()
    try:
        browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
    except Exception as e:
        logger.error(f"Failed to connect Playwright: {e}")
        await pw.__aexit__(None, None, None)
        return False

    if not browser.contexts:
        context = await browser.new_context()
    else:
        context = browser.contexts[0]

    page = context.pages[0] if context.pages else await context.new_page()

    # Use existing page if already on DAT (Octo profile often has power.dat.com open).
    # Only navigate if we're not on a DAT domain.
    current_url = page.url or ""
    if "dat.com" in current_url:
        logger.info(f"Already on DAT: {current_url}. Skipping navigation.")
    else:
        dat_search_url = "https://power.dat.com/"
        logger.info(f"Navigating to DAT: {dat_search_url}")
        try:
            await page.goto(dat_search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
        except Exception as e:
            # Don't close - profile may already have DAT open in another tab,
            # or user can navigate manually. Keep session.
            logger.warning(
                f"Navigation to DAT failed: {e}. Keeping browser open - "
                "navigate to power.dat.com manually if needed."
            )

    _scrape_session = {
        "pw_context": pw,
        "playwright": playwright,
        "browser": browser,
        "page": page,
    }
    logger.info("Scrape session opened. Browser ready for manual filters.")
    return True


async def dump_page_html_for_debug() -> Optional[str]:
    """Save the current page HTML to a file for DOM inspection. Returns path or None."""
    global _scrape_session
    if not _scrape_session:
        return None
    page = _scrape_session.get("page")
    if not page:
        return None
    try:
        html = await page.content()
        # Save to project_root/debug/dat_page_debug.html
        project_root = Path(__file__).resolve().parent.parent.parent
        debug_dir = project_root / "debug"
        debug_dir.mkdir(exist_ok=True)
        out_path = debug_dir / "dat_page_debug.html"
        out_path.write_text(html, encoding="utf-8")
        logger.info(f"Dumped page HTML to {out_path}")
        return str(out_path)
    except Exception as e:
        logger.error(f"Failed to dump page HTML: {e}")
        return None


async def close_scrape_session() -> None:
    """Close the stored browser connection if any."""
    global _scrape_session
    if not _scrape_session:
        return
    try:
        browser = _scrape_session.get("browser")
        pw_context = _scrape_session.get("pw_context")
        if browser:
            await browser.close()
        if pw_context:
            await pw_context.__aexit__(None, None, None)
    except Exception as e:
        logger.warning(f"Error closing scrape session: {e}")
    _scrape_session = None
    logger.info("Scrape session closed.")


async def scrape_and_store_from_open(max_loads: int = 20) -> int:
    """Scrape the currently visible loads from the open session and persist to DB.
    Does not close the browser. Returns number of new loads stored. Returns 0 if
    no session is open or on error."""
    global _scrape_session

    if not _scrape_session:
        logger.error("No scrape session open. Run /scrape_dat_open first.")
        return 0

    page = _scrape_session.get("page")
    if not page:
        logger.error("Scrape session has no page.")
        return 0

    start_time = time.time()
    loads_found = 0
    loads_new = 0
    loads_updated = 0
    status = "success"

    try:
        scraper = DATPlaywrightScraper(profile_uuid="")
        scraped = await scraper._extract_loads_from_page(page, max_loads)
        loads_found = len(scraped)

        with db.get_session() as session:
            for item in scraped:
                existing = session.query(Load).filter(Load.load_id == item.load_id).first()
                if item.broker_email:
                    broker = session.query(Broker).filter(Broker.email == item.broker_email).first()
                    if not broker:
                        broker = Broker(
                            name=item.broker_name or item.broker_email,
                            email=item.broker_email,
                            phone=item.broker_phone,
                            company=item.broker_name or "Unknown Broker",
                        )
                        session.add(broker)
                        session.flush()

                if existing:
                    loads_updated += 1
                    existing.origin = item.origin
                    existing.destination = item.destination
                    existing.miles = item.miles
                    existing.rate = item.rate
                    existing.equipment_type = item.equipment_type
                    existing.pickup_date = scraper._safe_parse_datetime(item.pickup_date)
                    existing.delivery_date = scraper._safe_parse_datetime(item.delivery_date)
                    existing.weight = item.weight
                    existing.commodity = item.commodity
                    existing.broker_name = item.broker_name
                    existing.broker_email = item.broker_email
                    existing.broker_phone = item.broker_phone
                    existing.dat_url = item.dat_url
                    existing.raw_data = json.dumps(item.raw_data)
                else:
                    loads_new += 1
                    load = Load(
                        load_id=item.load_id,
                        origin=item.origin,
                        destination=item.destination,
                        miles=item.miles,
                        rate=item.rate,
                        equipment_type=item.equipment_type,
                        pickup_date=scraper._safe_parse_datetime(item.pickup_date),
                        delivery_date=scraper._safe_parse_datetime(item.delivery_date),
                        weight=item.weight,
                        commodity=item.commodity,
                        broker_name=item.broker_name,
                        broker_email=item.broker_email,
                        broker_phone=item.broker_phone,
                        dat_url=item.dat_url,
                        status="new",
                        raw_data=json.dumps(item.raw_data),
                    )
                    session.add(load)

            duration = time.time() - start_time
            log = ScrapeLog(
                scrape_date=datetime.utcnow(),
                loads_found=loads_found,
                loads_new=loads_new,
                loads_updated=loads_updated,
                status=status,
                duration_seconds=duration,
            )
            session.add(log)
            session.commit()

        logger.info(f"Scrape from open session: found={loads_found}, new={loads_new}, updated={loads_updated}")
        return loads_new
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"scrape_and_store_from_open failed: {e}")
        logger.error(traceback.format_exc())
        with db.get_session() as session:
            log = ScrapeLog(
                scrape_date=datetime.utcnow(),
                loads_found=loads_found,
                loads_new=loads_new,
                loads_updated=loads_updated,
                status="error",
                error_message=str(e),
                duration_seconds=duration,
            )
            session.add(log)
            session.commit()
        return 0


class DATPlaywrightScraper:
    """Scraper that connects to DAT via an Octo-controlled Chromium instance using Playwright."""

    def __init__(self, profile_uuid: str) -> None:
        self.settings = config.settings
        self.profile_uuid = profile_uuid

        if not self.profile_uuid:
            logger.warning("No Octo profile UUID provided; DATPlaywrightScraper cannot start a profile.")

    async def scrape_and_store(self, max_loads: int = 20) -> int:
        """Public async entry-point: start Octo profile, attach via Playwright, scrape loads, persist them."""
        if not self.profile_uuid:
            logger.error("Cannot scrape: profile_uuid is empty.")
            return 0

        start_time = time.time()
        loads_found = 0
        loads_new = 0
        loads_updated = 0
        status = "success"
        error_message: Optional[str] = None

        try:
            scraped = await self._scrape_with_playwright(max_loads)
            loads_found = len(scraped)

            with db.get_session() as session:
                for item in scraped:
                    existing: Optional[Load] = session.query(Load).filter(Load.load_id == item.load_id).first()

                    # Ensure broker exists (if we have an email)
                    broker: Optional[Broker] = None
                    if item.broker_email:
                        broker = (
                            session.query(Broker)
                            .filter(Broker.email == item.broker_email)
                            .first()
                        )
                        if not broker:
                            broker = Broker(
                                name=item.broker_name or item.broker_email,
                                email=item.broker_email,
                                phone=item.broker_phone,
                                company=item.broker_name or "Unknown Broker",
                            )
                            session.add(broker)
                            session.flush()

                    if existing:
                        loads_updated += 1
                        existing.origin = item.origin
                        existing.destination = item.destination
                        existing.miles = item.miles
                        existing.rate = item.rate
                        existing.equipment_type = item.equipment_type
                        existing.pickup_date = self._safe_parse_datetime(item.pickup_date)
                        existing.delivery_date = self._safe_parse_datetime(item.delivery_date)
                        existing.weight = item.weight
                        existing.commodity = item.commodity
                        existing.broker_name = item.broker_name
                        existing.broker_email = item.broker_email
                        existing.broker_phone = item.broker_phone
                        existing.dat_url = item.dat_url
                        existing.raw_data = json.dumps(item.raw_data)
                    else:
                        loads_new += 1
                        load = Load(
                            load_id=item.load_id,
                            origin=item.origin,
                            destination=item.destination,
                            miles=item.miles,
                            rate=item.rate,
                            equipment_type=item.equipment_type,
                            pickup_date=self._safe_parse_datetime(item.pickup_date),
                            delivery_date=self._safe_parse_datetime(item.delivery_date),
                            weight=item.weight,
                            commodity=item.commodity,
                            broker_name=item.broker_name,
                            broker_email=item.broker_email,
                            broker_phone=item.broker_phone,
                            dat_url=item.dat_url,
                            status="new",
                            raw_data=json.dumps(item.raw_data),
                        )
                        session.add(load)

                duration = time.time() - start_time
                log = ScrapeLog(
                    scrape_date=datetime.utcnow(),
                    loads_found=loads_found,
                    loads_new=loads_new,
                    loads_updated=loads_updated,
                    status=status,
                    error_message=error_message,
                    duration_seconds=duration,
                )
                session.add(log)
                session.commit()

            logger.info(
                f"DAT scrape via Playwright complete: found={loads_found}, new={loads_new}, updated={loads_updated}"
            )
            return loads_new

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"DAT scrape via Playwright failed: {e}")
            logger.error(traceback.format_exc())
            with db.get_session() as session:
                log = ScrapeLog(
                    scrape_date=datetime.utcnow(),
                    loads_found=loads_found,
                    loads_new=loads_new,
                    loads_updated=loads_updated,
                    status="error",
                    error_message=str(e),
                    duration_seconds=duration,
                )
                session.add(log)
                session.commit()
            return 0

    # ---------- Playwright scraping ----------

    async def _scrape_with_playwright(self, max_loads: int) -> List[ScrapedLoad]:
        """Start Octo profile, attach via Playwright and read loads from the current DAT page."""
        scraped: List[ScrapedLoad] = []

        octo = OctoClient()
        ws_endpoint = await octo.start_profile_for_playwright(self.profile_uuid)
        logger.success(f"Octo returned ws_endpoint: {ws_endpoint}")
        if not ws_endpoint:
            logger.error("Octo did not return a ws_endpoint; aborting scrape.")
            return scraped

        async with async_playwright() as p:
            logger.info(f"Connecting to Octo CDP endpoint: {ws_endpoint}")
            browser = await p.chromium.connect_over_cdp(ws_endpoint)

            # Reuse existing context/page from Octo profile
            if not browser.contexts:
                context = await browser.new_context()
            else:
                context = browser.contexts[0]

            if context.pages:
                page = context.pages[0]
            else:
                page = await context.new_page()

            # Optional: ensure we are on the DAT loads page; if user already navigated there,
            # we can skip navigation.
            await self._ensure_on_loads_page(page)

            # Now scrape the visible table / cards.
            scraped = await self._extract_loads_from_page(page, max_loads)

            # Close only our side of the CDP connection; Octo keeps the profile running.
            await browser.close()

        return scraped

    async def _ensure_on_loads_page(self, page: Page) -> None:
        """Best-effort navigation to the main DAT loads screen."""
        url = page.url
        if "dat" not in url.lower():
            # If the user opened some other site in this profile, we can gently navigate.
            logger.info("Navigating to DAT Power homepage...")
            await page.goto("https://power.dat.com/", wait_until="networkidle")
            await asyncio.sleep(3)

        # At this point we assume the profile is logged in already.
        # You can add extra checks here (e.g. detecting a login form and bailing if found).

    async def _extract_loads_from_page(self, page: Page, max_loads: int) -> List[ScrapedLoad]:
        """Extract load rows from DAT One (one.dat.com/search-loads) results table.

        Uses data-test selectors from the DAT One Angular app.
        """
        scraped: List[ScrapedLoad] = []

        try:
            await page.wait_for_timeout(2000)
            await page.wait_for_selector("[data-test='results-table-body'] .row-container", timeout=15000)
        except Exception:
            logger.error("Could not find DAT loads table. Update selectors in DATPlaywrightScraper.")
            return scraped

        rows = await page.query_selector_all("[data-test='results-table-body'] .row-container")
        logger.info(f"Found {len(rows)} load rows on the page.")

        for row in rows[:max_loads]:
            await asyncio.sleep(0.2)

            async def get_text(sel: str) -> str:
                el = await row.query_selector(sel)
                if not el:
                    return ""
                txt = (await el.inner_text()) or ""
                return txt.strip()

            # DAT One selectors (data-test attributes)
            row_id = await row.get_attribute("id") or ""
            load_id = row_id.replace("table-row-", "") if row_id else ""
            if not load_id:
                load_id = f"dat-{int(time.time() * 1000)}"  # fallback

            # Origin: first city-state in orig-dest-container, or route-dh-container-lg .origin
            origin = await get_text("[data-test='load-origin-cell'] .city-state-container")
            if not origin:
                origin = await get_text(".route-dh-container-lg .origin")
            # Destination has its own data-test
            destination = await get_text("[data-test='load-destination-cell']")
            if not destination:
                destination = await get_text(".route-dh-container-lg .destination")

            if not origin or not destination:
                continue

            miles_text = await get_text("[data-test='load-trip-cell']")
            rate_el = await row.query_selector("[data-test='load-rate-cell'] .offer")
            rate_text = ""
            if rate_el:
                rate_text = (await rate_el.inner_text() or "").strip()
            if not rate_text:
                rate_el2 = await row.query_selector("[data-test='load-rate-cell'] .calculated-rate")
                if rate_el2:
                    rate_text = (await rate_el2.inner_text() or "").strip()
            equip_text = await get_text("[data-test='load-eq-cell']")
            pickup_text = await get_text("[data-test='load-pick-up-cell']")
            weight_text = await get_text("[data-test='load-weight-cell']")
            broker_name = await get_text("[data-test='load-company-cell']")

            contact_el = await row.query_selector("[data-test='load-contact-cell']")
            broker_email = ""
            broker_phone = ""
            if contact_el:
                href = await contact_el.get_attribute("href") or ""
                contact_txt = (await contact_el.inner_text() or "").strip()
                if "mailto:" in href:
                    broker_email = contact_txt
                elif "tel:" in href:
                    broker_phone = contact_txt
                elif contact_txt and "@" in contact_txt:
                    broker_email = contact_txt
                else:
                    broker_phone = contact_txt

            miles = self._parse_int(miles_text)
            rate = self._parse_money(rate_text)
            weight = self._parse_float(weight_text)

            raw = {
                "load_id": load_id,
                "origin": origin,
                "destination": destination,
                "miles": miles_text,
                "rate": rate_text,
                "equipment_type": equip_text,
                "pickup": pickup_text,
                "weight": weight_text,
                "broker_name": broker_name,
                "broker_email": broker_email,
                "broker_phone": broker_phone,
            }

            scraped.append(
                ScrapedLoad(
                    load_id=load_id,
                    origin=origin,
                    destination=destination,
                    miles=miles,
                    rate=rate,
                    equipment_type=equip_text or None,
                    pickup_date=pickup_text or None,
                    delivery_date=None,
                    weight=weight,
                    commodity=None,
                    broker_name=broker_name or None,
                    broker_email=broker_email or None,
                    broker_phone=broker_phone or None,
                    dat_url=None,
                    raw_data=raw,
                )
            )

        return scraped

    # ---------- Parsing helpers ----------

    @staticmethod
    def _parse_int(text: str) -> Optional[int]:
        if not text:
            return None
        digits = "".join(ch for ch in text if ch.isdigit())
        try:
            return int(digits) if digits else None
        except ValueError:
            return None

    @staticmethod
    def _parse_float(text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = text.replace(",", "").replace(" ", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _parse_money(text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = text.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _safe_parse_datetime(text: Optional[str]) -> Optional[datetime]:
        if not text:
            return None
        # For now, store dates as strings in raw_data and leave parsed fields optional.
        # You can implement custom parsing here if DAT exposes a stable date format.
        return None

