"""Configuration variables for the Elgiva Theatre scraper."""

# Target URL listing mappings associated with expected validation category codes
PAGES = [
    ("https://elgiva.com/book-a-show/musical-theatre/", "musical"),
    ("https://elgiva.com/book-a-show/theatre/", "play"),
]

# Web Interface Interaction Element Mapping Rules
SELECTORS = {
    "cookie_btn": "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "event_cards": "article.elementor-post",
    "event_link_anchor": "h2.elementor-post__title a",
    "performance_rows": "tr[class*='dot_events_day_']",
    "performance_links": "td a",
    "spektrix_iframe": "SpektrixIFrame",
    "seating_area_images": "div.SeatingArea img",
    "venue_address_block": "//p[contains(., 'St Mary’s Way')]",
    "venue_fallback_block": "//p[contains(text(), 'Our address is')]",
}

# Framework Control Constants
DEFAULT_CURRENCY = "GBP"
DEFAULT_COUNTRY = "UK"