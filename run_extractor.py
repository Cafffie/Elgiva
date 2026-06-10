"""Elgiva Theatre extractor module adhering to the BaseExtractor framework lifecycle."""

import json
import re
import sys
from datetime import datetime
import pandas as pd
from selenium.webdriver.common.by import By
from seleniumbase import SB

from utils.base_extractor import BaseExtractor
from utils.logger import setup_logger
from utils.scraping_helpers import (
    get_scrape_datetime,
    human_delay,
    human_scroll,
    normalize_country,
    standardize_category,
)

from .elgiva_config import DEFAULT_COUNTRY, DEFAULT_CURRENCY, PAGES, SELECTORS

logger = setup_logger(__name__, log_to_file=False)


class ElgivaExtractor(BaseExtractor):
    """ETL Pipeline Extractor for structural theatre data from elgiva.com."""

    def __init__(self, local_test=False, show_count=None, headless=True,**kwargs):
        super().__init__(
            site_id="elgiva",
            log_to_file=False,
            log_to_terminal=True,
            **kwargs,
        )
        self.local_test = local_test
        self.show_count = show_count
        self.all_rows = []
        self.headless = headless

    def extract(self, *args, **kwargs):
        """No-op execution hook since Pattern A relies on streaming inside run()."""
        pass

    def _parse(self, _raw=None) -> pd.DataFrame:
        """Pure operational interface converting buffered items to validation DataFrame."""
        canonical_columns = [
            "title", "venue_url", "category", "venue", "address", "city", "country",
            "open_date", "close_date", "booking_start_date", "booking_end_date",
            "upcoming_performances", "capacity", "currency", "is_limited_run",
            "seat_pricing", "scrape_datetime"
        ]
        if self.all_rows:
            df = pd.DataFrame(self.all_rows)
            df = df.reindex(columns=canonical_columns)
        else:
            df = pd.DataFrame(columns=canonical_columns)
        
        self.custom_logger.info("Parsing completed. Extracted %s shows", len(df))
        return df

    def run(self):
        """Orchestrates active browser engine sessions and pushes data to frames."""
        try:
            # uc=True handles anti-bot detection; headless managed by internal framework flags
            with SB(uc=True, headless=self.headless) as sb:
                sb.driver.implicitly_wait(5)
                seen_urls = set()
                
                for page_idx, (url, category) in enumerate(PAGES, start=1):
                    self.custom_logger.info(
                        f"Category Crawl [{page_idx}/{len(PAGES)}] → {category}"
                    )
                    
                    if hasattr(sb, "activate_cdp_mode"):
                        sb.activate_cdp_mode()
                    elif hasattr(sb, "activate_cdp"):
                        sb.activate_cdp()

                    sb.open(url)
                    self._handle_cookies(sb)
                    human_scroll(sb.driver)
                    
                    shows = self._extract_event_list(sb, category)
                    if self.local_test and self.show_count:
                        shows = shows[:self.show_count]

                    for i, show in enumerate(shows, start=1):
                        if show["event_url"] in seen_urls:
                            self.custom_logger.info(
                                f"Skipping duplicate event: {show['title']}"
                            )
                            continue
                        seen_urls.add(show["event_url"])

                        self.custom_logger.info(
                            f"Extracting Show Details [{i}/{len(shows)}] → '{show['title']}'"
                        )
                        sb.open(show["event_url"])
                        self._handle_cookies(sb)
                        human_scroll(sb.driver)
                        
                        # Phase 1: Venue Metadata Parsing
                        venue_details = self._get_venue_details(sb)
                        
                        # Phase 2: Performance Tracking
                        raw_performances = self._extract_performances_from_table(sb)
                        if not raw_performances:
                            self.custom_logger.warning(
                                f"Skipping '{show['title']}' — No functional performances listed."
                            )
                            continue
                        
                        performance_dates = [p["date"] for p in raw_performances]
                        open_date = min(performance_dates) if performance_dates else ""
                        close_date = max(performance_dates) if performance_dates else ""
                        
                        formatted_performances = repr([
                            {"date": p["date"], "time": p["time"]} for p in raw_performances
                        ])
                        
                        # Phase 3: Seat Mapping & Costing Breakdown
                        seat_pricing, detected_currency = self._extract_all_seats(sb, raw_performances)
                        formatted_seat_pricing = repr(seat_pricing)
                        
                        capacity = max([p.get("capacity", 0) for p in raw_performances], default=0)
                        final_currency = detected_currency or DEFAULT_CURRENCY
                        
                        # Structure final row exactly according to schema types
                        row = {
                            "title": show["title"],
                            "venue_url": show["event_url"],
                            "category": standardize_category(show["category"]),
                            "venue": venue_details["venue"],
                            "address": venue_details["address"],
                            "city": venue_details["city"],
                            "country": normalize_country(venue_details["country"]),
                            "open_date": open_date,
                            "close_date": close_date,
                            "booking_start_date": open_date,
                            "booking_end_date": close_date,
                            "upcoming_performances": formatted_performances,
                            "capacity": int(capacity) if capacity > 0 else None,
                            "currency": final_currency.upper(),
                            "is_limited_run": True,
                            "seat_pricing": formatted_seat_pricing,
                            "scrape_datetime": get_scrape_datetime(),
                        }
                        
                        self.all_rows.append(row)
                        self.log_record(row)

            # Trigger downstream verification checks
            df = self._parse()
            return self._run_post_parse(df, raw_key="elgiva_live_stream")

        except Exception as e:
            return self._finalize_failure(e, df=None)

    # ─────────────────────────────────────────────────────────────────────────
    # Modular Internal Helper Methods
    # ─────────────────────────────────────────────────────────────────────────────

    def _handle_cookies(self, sb):
        """Safely signs off or passes privacy consent blockages."""
        try:
            if sb.is_element_visible(SELECTORS["cookie_btn"]):
                sb.click(SELECTORS["cookie_btn"])
                human_delay(0.5, 1.0)
        except Exception:
            pass

    def _get_venue_details(self, sb):
        """Extracts and normalizes geographic positioning fields."""
        details = {
            "venue": "The Elgiva",
            "address": "St Mary’s Way",
            "city": "Chesham",
            "country": DEFAULT_COUNTRY
        }
        try:
            if sb.is_element_present(SELECTORS["venue_address_block"]):
                elements = sb.find_elements(By.XPATH, SELECTORS["venue_address_block"])
                for el in elements:
                    lines = [line.strip() for line in el.text.split('\n') if line.strip()]
                    if len(lines) >= 3 and "our address" not in lines[0].lower():
                        details["venue"] = lines[0]
                        details["address"] = lines[1]
                        details["city"] = lines[2]
                        return details

            if sb.is_element_present(SELECTORS["venue_fallback_block"]):
                fallback_text = sb.get_text(SELECTORS["venue_fallback_block"])
                match = re.search(r"Our address is\s+([^.]+)", fallback_text, re.IGNORECASE)
                if match:
                    parts = [p.strip() for p in match.group(1).split(',')]
                    if len(parts) >= 3:
                        details["venue"] = parts[0]
                        details["address"] = parts[1]
                        details["city"] = parts[2]
        except Exception as e:
            self.custom_logger.warning(f"Venue deduction issue, applying configuration fallback: {e}")
        return details

    def _extract_event_list(self, sb, category):
        """Builds collection lists tracking internal production navigation records."""
        show_links = []
        try:
            sb.wait_for_ready_state_complete()
            sb.sleep(3)
            sb.wait_for_element_present(SELECTORS["event_cards"], timeout=15)
            shows = sb.find_elements(By.CSS_SELECTOR, SELECTORS["event_cards"])
            self.custom_logger.info(
                f"Found cards: {len(shows)} using selector {SELECTORS['event_cards']}"
            )
            for show in shows:
                try:
                    link_el = show.find_element(By.CSS_SELECTOR, SELECTORS["event_link_anchor"])
                    show_links.append({
                        "title": link_el.get_attribute("textContent").strip(),
                        "event_url": link_el.get_attribute("href"),
                        "category": category
                    })
                except Exception:
                    continue
            
        except Exception as e:
            self.custom_logger.error(f"Failed to query production listing grid cards: {e}")
        return show_links

    def _clean_time_string(self, time_element):
        """Translates localized UI variants safely into standard 24-Hour expressions."""
        try:
            raw_text = time_element.text.strip().lower()
            span_el = time_element.find_element(By.CSS_SELECTOR, "span")
            span_text = span_el.text.strip()
            
            match = re.search(r"(\d+):(\d+)", span_text)
            if not match:
                return ""
            hour = int(match.group(1))
            minute = int(match.group(2))
            
            if "pm" in raw_text and hour < 12:
                hour += 12
            elif "am" in raw_text and hour == 12:
                hour = 0
                
            return f"{hour:02d}:{minute:02d}"
        except Exception:
            return ""




    def _extract_performances_from_table(self, sb):
        """Scrapes performance dates and operational transaction links."""
        perf_list = []
        self.custom_logger.info(f"DEBUG By = {By}")
        self.custom_logger.info(f"DEBUG SELECTOR = {SELECTORS['performance_rows']}")
        try:
            # Check if performance rows selector is present
            try:
                rows = sb.find_elements(By.CSS_SELECTOR, SELECTORS["performance_rows"])
                self.custom_logger.info(f"Found {len(rows)} performance rows")
            except Exception as find_error:
                self.custom_logger.warning(
                    f"Could not find performance rows with selector '{SELECTORS['performance_rows']}': {find_error}"
                )
                return perf_list
            
            if not rows:
                self.custom_logger.warning(f"No performance rows found using selector: {SELECTORS['performance_rows']}")
                return perf_list
                
            for row in rows:
                try:
                    class_attr = row.get_attribute("class") or ""
                    date_match = re.search(r"dot_events_day_(\d{4})(\d{2})(\d{2})", class_attr)
                    if not date_match:
                        continue
                        
                    iso_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                    self.custom_logger.info(f"Processing performances for date: {iso_date}")
                    
                    # Get the outerHTML of the row to extract performance links
                    row_html = row.get_attribute("outerHTML") or ""
                    
                    # Parse performance links from HTML using regex
                    # Look for <a> tags with href and time content like <span>1:00</span>pm
                    link_pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>\s*<span[^>]*>(\d+):(\d+)</span>\s*(am|pm)'
                    matches = re.finditer(link_pattern, row_html, re.IGNORECASE)
                    
                    for match in matches:
                        booking_url = match.group(1)
                        hour = int(match.group(2))
                        minute = int(match.group(3))
                        am_pm = match.group(4).lower()
                        
                        # Convert to 24-hour format
                        if am_pm == 'pm' and hour != 12:
                            hour += 12
                        elif am_pm == 'am' and hour == 12:
                            hour = 0
                        
                        iso_time = f"{hour:02d}:{minute:02d}"
                        
                        perf_list.append({
                            "date": iso_date,
                            "time": iso_time,
                            "booking_url": booking_url,
                            "sold_out": False  # Check if marked as sold out if needed
                        })
                        
                except Exception as row_error:
                    self.custom_logger.warning(f"Error processing performance row: {row_error}")
                    continue
                    
        except Exception as e:
            self.custom_logger.error(f"Critical error reading performance matrices tables: {e}")
        
        self.custom_logger.info(f"Successfully extracted {len(perf_list)} performances")
        return perf_list

    def _extract_all_seats(self, sb, performances):
        """Traverses isolated Spektrix modal states to extract ticket pricing metadata."""
        seat_pricing = {}
        detected_currency = None

        for perf in performances:
            if not perf["booking_url"] or perf["sold_out"]:
                continue
                
            try:
                sb.open(perf["booking_url"])
                human_delay(1.0, 2.0)
                
                # Dynamic context-switch verification targeting Spektrix containers
                sb.wait_for_element_present(f"iframe#{SELECTORS['spektrix_iframe']}", timeout=6)
                sb.switch_to_frame(f"iframe#{SELECTORS['spektrix_iframe']}")
                
                sb.wait_for_element_present(SELECTORS["seating_area_images"], timeout=6)
                seats = sb.find_elements(By.CSS_SELECTOR, SELECTORS["seating_area_images"])
                
                seat_list = []
                for seat in seats:
                    tooltip = seat.get_attribute("tooltip") or seat.get_attribute("title") or ""
                    if not tooltip:
                        continue
                        
                    if "£" in tooltip and not detected_currency:
                        detected_currency = "GBP"
                        
                    match = re.search(r"([A-Z]+\d+)\s*-\s*£?([\d,.]+)", tooltip)
                    if match:
                        seat_list.append({
                            "seat": match.group(1),
                            "ticket_price": float(match.group(2).replace(",", ""))
                        })
                        
                perf["capacity"] = len(seats)
                key = f"{perf['date']} {perf['time']}"
                seat_pricing[key] = seat_list
                
            except Exception as e:
                self.custom_logger.warning(
                    f"Skipping seat map mapping for {perf['date']} {perf['time']} due to timeout/error: {e}"
                )
            finally:
                try:
                    sb.switch_to_default_content()
                except Exception:
                    pass
                    
        return seat_pricing, detected_currency


def main():
    """Execution endpoint targeting local verification patterns."""
    extractor = ElgivaExtractor(save_csv_locally=True, local_test=True, show_count=2)
    result = extractor.run()
    logger.info(f"Test Pipeline Outcome: {result}")


if __name__ == "__main__":
    main()