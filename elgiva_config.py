"""Configuration for Elgiva Theatre (elgiva.com) scraper."""

SITE_ID = "elgiva"
BASE_URL = "https://elgiva.com"

PAGES = [
    (f"{BASE_URL}/book-a-show/musical-theatre/", "Musical"),
    (f"{BASE_URL}/book-a-show/theatre/", "Play"),
]

COOKIE_BTN_XPATH = "//button[@id='CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll']"

HEADLESS = True
PAGE_LOAD_TIMEOUT = 60
IFRAME_WAIT_TIMEOUT = 5
SEAT_WAIT_TIMEOUT = 5

DELAY_BETWEEN_SHOWS = (2, 4)
DELAY_BETWEEN_PERFS = (1, 3)
