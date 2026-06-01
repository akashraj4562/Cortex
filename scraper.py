import re
import requests
from bs4 import BeautifulSoup
from config import SCRAPER_TIMEOUT


def is_url(text):
    text = text.strip()
    return bool(re.match(r'^https?://', text) or re.match(r'^www\.', text))


def scrape(url):
    """Return plain text content from URL, or None on failure."""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=SCRAPER_TIMEOUT)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # LinkedIn job pages: prioritize job description div
    jd_div = soup.find("div", {"class": re.compile(r"description|job-detail", re.I)})
    if jd_div:
        return _clean(jd_div.get_text())

    # Generic: get main content area or body
    main = soup.find("main") or soup.find("article") or soup.body
    if main:
        return _clean(main.get_text())

    return _clean(soup.get_text())


def _clean(text):
    lines = [line.strip() for line in text.splitlines()]
    lines = [l for l in lines if l]
    text = "\n".join(lines)
    # Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text[:8000]  # Cap at 8k chars to keep Claude calls fast
