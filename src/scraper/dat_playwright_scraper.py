"""DAT scraper driven by Octo Browser + Playwright.

This scraper assumes:
- Octo Browser desktop app is running on the same host.
- We start a profile for automation using the local Octo API
  (http://host.docker.internal:58888/api/profiles/start) and get a ws_endpoint.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from playwright.async_api import async_playwright, Page

from src.utils.logger import logger
from src.utils.config import config
from src.octo.client import OctoClient
from src.database.database import db
from src.database.models import Load, Broker, ScrapeLog


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
        """Extract load rows/cards from the current DAT page.

        NOTE: All CSS selectors here are placeholders. You will need to:
        - Inspect the DAT DOM in the Octo profile
        - Update the selectors to match actual class names / structure
        """
        scraped: List[ScrapedLoad] = []

        # Example: wait for a generic table of loads to appear.
        # Replace `.loads-table` and `tr.load-row` with real selectors from DAT.
        try:
            await page.wait_for_timeout(2000)  # small pause to mimic human behaviour
            await page.wait_for_selector("table tbody tr", timeout=15000)
        except Exception:
            logger.error("Could not find DAT loads table. Update selectors in DATPlaywrightScraper.")
            return scraped

        rows = await page.query_selector_all("table tbody tr")
        logger.info(f"Found {len(rows)} potential load rows on the page.")

        for row in rows[:max_loads]:
            # Small delay between rows to keep tempo human-like
            await asyncio.sleep(0.3)

            def _safe_inner_text(selector: str) -> str:
                return ""

            # Use closures with async/await for Playwright
            async def get_text(sel: str) -> str:
                el = await row.query_selector(sel)
                if not el:
                    return ""
                txt = (await el.inner_text()) or ""
                return txt.strip()

            # Placeholder selectors; adjust to real DAT layout.
            load_id = await get_text(".load-id")
            origin = await get_text(".origin")
            destination = await get_text(".destination")

            if not load_id or not origin or not destination:
                # Skip rows that don't look like real loads
                continue

            miles_text = await get_text(".miles")
            rate_text = await get_text(".rate")
            equip_text = await get_text(".equipment")
            pickup_text = await get_text(".pickup")
            delivery_text = await get_text(".delivery")
            weight_text = await get_text(".weight")
            commodity_text = await get_text(".commodity")

            broker_name = await get_text(".broker-name")
            broker_email = await get_text(".broker-email")
            broker_phone = await get_text(".broker-phone")

            dat_url = None
            link_el = await row.query_selector("a.load-link")
            if link_el:
                dat_url = await link_el.get_attribute("href")

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
                "delivery": delivery_text,
                "weight": weight_text,
                "commodity": commodity_text,
                "broker_name": broker_name,
                "broker_email": broker_email,
                "broker_phone": broker_phone,
                "dat_url": dat_url,
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
                    delivery_date=delivery_text or None,
                    weight=weight,
                    commodity=commodity_text or None,
                    broker_name=broker_name or None,
                    broker_email=broker_email or None,
                    broker_phone=broker_phone or None,
                    dat_url=dat_url,
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

