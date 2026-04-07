#!/usr/bin/env python3
"""
Judicial & Tribunal Vacancy Scraper - India
Fetches real-time vacancy data from official government portals.
Run daily: python3 scraper.py
"""

import requests
from bs4 import BeautifulSoup, Tag
import feedparser
import json
import os
import re
import time
import urllib3
from datetime import datetime, timedelta
from urllib.parse import urljoin

# Suppress InsecureRequestWarning for verify=False calls
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TIMEOUT = 15
TODAY = datetime.now().date()

data = {
    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "sources": [],
    "vacancies": [],
    "news": [],
    "errors": []
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def safe_fetch(url, label, verify=True):
    """Fetch a URL safely, return (soup, True) or (None, False)."""
    try:
        log(f"Fetching: {label} ({url})")
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        data["sources"].append({"name": label, "url": url, "status": "ok", "fetched_at": datetime.now().isoformat()})
        return soup, True
    except Exception as e:
        # If SSL verification fails, retry with verify=False
        if verify and "SSL" in str(e).upper():
            log(f"  SSL error, retrying with verify=False...")
            try:
                resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                data["sources"].append({"name": label, "url": url, "status": "ok", "fetched_at": datetime.now().isoformat()})
                return soup, True
            except Exception as e2:
                e = e2
        err = f"Failed to fetch {label}: {str(e)}"
        log(f"  ERROR: {err}")
        data["errors"].append(err)
        data["sources"].append({"name": label, "url": url, "status": "error", "error": str(e)})
        return None, False


def safe_rss(url, label):
    """Fetch an RSS feed safely."""
    try:
        log(f"Fetching RSS: {label} ({url})")
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            raise Exception(f"Feed parse error: {feed.bozo_exception}")
        data["sources"].append({"name": label, "url": url, "status": "ok", "fetched_at": datetime.now().isoformat()})
        return feed, True
    except Exception as e:
        err = f"Failed to fetch RSS {label}: {str(e)}"
        log(f"  ERROR: {err}")
        data["errors"].append(err)
        data["sources"].append({"name": label, "url": url, "status": "error", "error": str(e)})
        return None, False


# ============================================================
# VACANCY TITLE FILTER — reject junk scraped from nav/page chrome
# ============================================================

# Titles that are clearly NOT vacancy listings
JUNK_TITLES_EXACT = {
    "about us", "contact us", "latest updates", "latest update", "home",
    "links", "past members", "judicial information", "notice board",
    "judicial members", "technical members", "status of members",
    "organization structure", "court display board", "diary status",
    "court master", "click here", "jurisdiction", "chairperson and members",
    "rti orders", "rti orders & circulars", "it judicial section",
    "daily cause list", "daily orders", "tentative cause list",
    "reportable judgements", "large bench orders", "review cases of regional benches",
    "larger bench circulars", "matters referred under sec 28",
    "all high courts", "consumer advocacy", "visit reports",
    "electricity ombudsman", "about electricity ombudsman",
    "format for representation", "format for representation before electricity ombudsman",
    "final orders issued by electricity ombudsman",
    "daily orders issued by electricity ombudsman",
    "hearing schedule", "electricity ombudsman hearing schedule",
    "contact list", "calendars", "notifications", "photo gallery",
    "aft act & rules", "army act & rules", "navy act & rules",
    "air force act & rules", "rti principal bench", "goi directory",
    "appellate tribunal", "real estate appellate tribunal",
    "judgements passed by real estate appellate tribunal",
    "public notices by appellate tribunal", "orders/ judgements by appellate tribunal",
    "orders/ judgements in execution by appellate tribunal",
    "form l - appeal to appellate tribunal under section 44 of the act",
    "judicial academy", "mperc vacancy",
    "constitution of electricity ombudsman & the cgrfs",
    "former chairperson and members of the commission",
    "vacancies", "notifications", "calendars", "photo gallery",
    "she-box online complaint", "national portal of india",
    "supreme court of india", "delhi district court",
    "central administrative tribunal (cat)", "goi directory",
    "recruitment news", "recruitment rules", "recruitments",
    "appointment orders", "gstat recruitment", "judgements in aft pb",
    "rti regional benches", "srinagar - cause list", "srinagar - judgement",
    "recruitment results", "recruitment result",
    "letter of judicial matter", "judicial academy",
    "maharashtra judicial academy",
    "electricity act 2003", "other electricity acts",
    "policies under the act", "information under section 62(5) of the act",
    "individual regulation", "consolidated regulation",
    "draft regulation / discussion paper", "technical validation",
    "market monitoring reports", "advice to government",
    "notice board (judicial info)",
}

# Regex patterns for junk titles
JUNK_TITLE_PATTERNS = [
    re.compile(r"^(circulars?\/?(\s*o\.?m\.?)?\/?(\s*orders?)?)$", re.I),
    re.compile(r"^profile\s+of\s+", re.I),
    re.compile(r"^former\s+(chairperson|chaiperson|president|member)", re.I),
    re.compile(r"^previous\s+(chairperson|president|member)", re.I),
    re.compile(r"^chairperson\s*and\s*members?\b", re.I),
    re.compile(r"^chairpersons?\s*,?\s*members?\s*&\s*officers", re.I),
    re.compile(r"^sitting\s+members", re.I),
    re.compile(r"^members?\s*&\s*officers", re.I),
    re.compile(r"^nomination\s+of\s+(former|newly)", re.I),
    re.compile(r"^postings?\s+of\s+newly", re.I),
    re.compile(r"^relief\s+arrangements", re.I),
    re.compile(r"^gazette.?notification", re.I),
    re.compile(r"engagement\s+of\s+staff\s+consultants", re.I),
    re.compile(r"^©\d", re.I),
    re.compile(r"^(cause\s*list|judgement|chandigarh|chennai|guwahati|kochi|jabalpur|mumbai|kolkata|lucknow|jaipur)\s*[-–]?\s*(cause\s*list|judgement|causelist)?$", re.I),
    re.compile(r"^(allahabad|andhra\s*pradesh|bombay|calcutta|chhattisgarh|delhi|gauhati|himachal|jammu|jharkhand|karnataka|kerala|madhya\s*pradesh|madras|manipur|meghalaya|orissa|patna|punjab|rajasthan|sikkim|telangana|tripura|uttarakhand|gujarat)\s*(high\s*court)?$", re.I),
    re.compile(r"^high\s*court\s*of\s+\w+$", re.I),
    re.compile(r"^(national\s+company\s+law\s+(tribunal|appellate)|insolvency\s+and\s+bankruptcy|ministry\s+of\s+co[rp]+orate)", re.I),
    re.compile(r"^राष्ट्रीय|^उपभोक्ता", re.I),
    re.compile(r"^district\s+and\s+sessions\s+judge\s+\w+$", re.I),
    re.compile(r"^corrigendum\s*:?\s*$", re.I),
    re.compile(r"^tribunals?\s*[-–]?\s*(merger)?$", re.I),
    re.compile(r"^aft\s+cases\s+appealed", re.I),
    re.compile(r"^gstat\.?\d?\.pdf$", re.I),
    re.compile(r"^former\s+(chief\s+)?justices?", re.I),
    re.compile(r"^previous\s+chairpersons", re.I),
    re.compile(r"^chairperson\s+and\s+members\s+\w+$", re.I),
    re.compile(r"^public\s+notice\s+in\s+the\s+matter\s+of\s+draft\s+revision", re.I),
]

# Partial-match junk patterns — match ANYWHERE in title (not just start)
# These are process noise: results, merit lists, corrigendums, candidate lists
JUNK_PARTIAL_PATTERNS = re.compile(
    r"result\s+(for|of)\s+(engagement|combined|the)|"
    r"merit\s+list|panel\s*\(wait|skill\s+test|"
    r"list\s+of\s+(candidates|ineligible|eligible)|"
    r"cancellation\s+of|corrigendum|deferred|rescheduling|"
    r"departmental\s+qualifying|visit\s+reports?|former\s+registrar|"
    r"order\s+regarding\s+empanelled|circular\s+a-?\d+|"
    r"mark\s+list|centre\s*wise\s+list|select\s+list\s+of\s+candidates|"
    r"model\s+answer|notification\s+(comprising|along\s*with)\s+list|"
    r"found\s+(in)?eligible|cancellation\s+of\s+candidature|"
    r"provisionally\s+eligible|^https?://|"
    r"national\s+judicial\s+academy|faculty\s+for\s+physical|"
    r"engagement\s+of\s+staff\s+consultants|"
    r"information\s+under\s+section|"
    r"appointment\s+of\s+(hon.ble\s+)?chairperson\s+and\s+members\s+\d",
    re.I,
)

# Keywords that indicate an actual vacancy/recruitment
VACANCY_KEYWORDS = re.compile(
    r"vacancy|vacanc|recruit|appoint|application|filling|selection|"
    r"advertis|engagement|invitation|inviting|direct\s+recruitment|"
    r"hiring|post\s+of|posts\s+of|walk.in|interview|circular.*post|"
    r"empanelment|online\s+applications?|deputation|cadre|"
    r"law\s+clerk|stenograph|registrar|member.*tribunal|"
    r"presiding\s+officer|chairperson.*drat|judicial\s+service",
    re.I,
)


def is_vacancy_title(title):
    """Return True if the title looks like an actual vacancy/recruitment item."""
    t = " ".join((title or "").split()).strip()
    if len(t) < 5:
        return False
    tl = t.lower()
    if tl in JUNK_TITLES_EXACT:
        return False
    for pat in JUNK_TITLE_PATTERNS:
        if pat.match(t):
            return False
    # Partial-match junk (results, corrigendums, candidate lists, etc.)
    if JUNK_PARTIAL_PATTERNS.search(t):
        return False
    # If it has a vacancy keyword, keep it
    if VACANCY_KEYWORDS.search(t):
        return True
    # Short generic titles without vacancy keywords are junk
    if len(t) < 20:
        return False
    return True


# ============================================================
# LEGAL/JUDICIAL ROLE FILTER — only keep jobs relevant to lawyers
# ============================================================

# Positions that are clearly non-legal (engineering, clerical, managerial, technical)
NON_LEGAL_ROLES = re.compile(
    r"\b(engineer|technician|apprentice|mining\s*sirdar|overman|"
    r"driver|peon|ardali|teacher|jbt\b|manager|deputy\s*manager|"
    r"assistant\s*manager|programmer|computer|accountant|accounts\s*officer|"
    r"stenograph|ldc\b|udc\b|lower\s*division\s*clerk|upper\s*division\s*clerk|"
    r"typist|excise\s*inspector|laboratory|data\s*entry|"
    r"private\s*secretary|pps\b|hindi\s*translat|"
    r"staff\s*car|group\s*[cd]\b|sweeper|chowkidar|daftary|"
    r"court\s*assistant.*technical|npcil|nhpc\b|mcl\b|gsl\b|"
    r"psssb|drdo\b|mpfsl|trainee\s*engineer)\b",
    re.I,
)

# Keywords that confirm a legal/judicial/lawyer role
LEGAL_ROLE_KEYWORDS = re.compile(
    r"\b(judicial|judge|district\s*judge|lawyer|advocate|legal|"
    r"law\s*clerk|presiding\s*officer|member.*tribunal|member.*commission|"
    r"judicial\s*service|judicial\s*member|technical\s*member|"
    r"chairperson|registrar|joint\s*registrar|deputy\s*registrar|"
    r"assistant\s*registrar|notary|lokayukta|ombudsman|"
    r"arbitrat|mediator|presenting\s*officer|"
    r"consumer.*commission|member.*ncdrc|member.*nclat|member.*nclt|"
    r"member.*cat\b|member.*sat\b|member.*itat\b|member.*drat\b|"
    r"member.*ngt\b|member.*aft\b|member.*cestat\b|member.*gstat\b|"
    r"member.*rct\b|member\s*\(law\)|member\s*\(judicial\)|"
    r"vacancy\s*circular.*member|selection.*member|"
    r"superior\s*judicial|higher\s*judicial|civil\s*judge|"
    r"senior\s*civil\s*judge|munsif|magistrate|"
    r"tribunal.*recruitment|tribunal.*vacanc|tribunal.*appointment|"
    r"high\s*court.*recruit|high\s*court.*vacanc)\b",
    re.I,
)

# Sources that are inherently legal/judicial — trust their content
LEGAL_SOURCES = {
    "Dept of Legal Affairs", "Dept of Justice", "NCLT", "NCLAT", "MCA Portal",
    "ITAT", "GSTAT", "CERC", "DRT/DRAT", "Ministry of Finance - DRT",
    "Railway Claims Tribunal", "APTEL", "TDSAT", "SAT",
    "NCDRC", "NHRC", "Lokpal", "Consumer Affairs Ministry",
    "Allahabad HC", "Delhi HC", "Telangana HC", "Jharkhand HC",
    "Gauhati HC", "Gujarat HC", "Madras HC",
    "Bombay HC", "Calcutta HC", "Karnataka HC", "Kerala HC",
    "MP HC", "Punjab & Haryana HC", "Rajasthan HC", "AP HC",
    "Patna HC", "Orissa HC", "Meghalaya HC", "Tripura HC",
    "Himachal Pradesh HC", "Supreme Court",
    "NGT", "CAT", "CESTAT", "CCI", "IBBI", "CGIT",
    "NALSA", "Law Commission", "SEBI",
    "Verdictum", "LiveLaw - Presiding Officer",
    "CIC", "IRDAI", "NFRA", "PFRDA", "Confonet",
    "AP SIC", "Telangana SIC", "Maharashtra SIC",
    "Maharashtra AT", "Karnataka AT",
    "UP ERC", "Chhattisgarh ERC", "Rajasthan ERC", "Haryana ERC",
    "Tamil Nadu ERC", "AP ERC", "Kerala ERC",
    "Karnataka RERA", "Rajasthan RERA", "UP RERA",
    "Tamil Nadu RERA", "Gujarat RERA", "Maharashtra RERA",
}


def is_legal_role(vacancy):
    """Return True if the vacancy is relevant to lawyers/legal professionals."""
    title = " ".join((vacancy.get("title", "")).split()).strip()
    source = vacancy.get("source", "")
    category = vacancy.get("category", "")

    # If title explicitly mentions non-legal roles AND no legal keyword, reject
    if NON_LEGAL_ROLES.search(title) and not LEGAL_ROLE_KEYWORDS.search(title):
        return False

    # If title has a legal keyword, always keep
    if LEGAL_ROLE_KEYWORDS.search(title):
        return True

    # Trusted legal sources — keep unless explicitly non-legal (already checked above)
    if source in LEGAL_SOURCES:
        return True

    # Category-based trust
    legal_categories = {"Central Tribunal", "Tribunal Vacancy", "High Court - Tribunal Vacancy",
                        "Consumer Commission", "Anti-Corruption", "Debt Recovery Tribunal",
                        "Electricity Tribunal", "Telecom Tribunal", "Securities Tribunal"}
    if category in legal_categories:
        return True

    # GovtJobGuru/LiveLaw/aggregators — only keep if title has legal keywords
    # (already checked above, so if we're here, it doesn't)
    if source in {"GovtJobGuru", "LiveLaw"}:
        return False

    return True


def add_vacancy(vacancy):
    """Add a vacancy only if it's a real vacancy listing for legal/judicial roles."""
    title = vacancy.get("title", "")
    if not is_vacancy_title(title):
        log(f"    SKIPPED (not a vacancy): {title[:80]}")
        return False
    if not is_legal_role(vacancy):
        log(f"    SKIPPED (non-legal role): {title[:80]}")
        return False
    # Must have at least one date (deadline or posted date)
    if not vacancy.get("last_date") and not vacancy.get("posted_date"):
        log(f"    SKIPPED (no date at all): {title[:80]}")
        return False
    data["vacancies"].append(vacancy)
    return True


# ============================================================
# DATE EXTRACTION UTILITIES
# ============================================================

# Month name mappings for parsing
MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Regex patterns for various date formats
DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    (r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', 'dmy_numeric'),
    # YYYY-MM-DD (ISO format)
    (r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', 'ymd_numeric'),
    # DD Month YYYY or DD Month, YYYY (e.g., "15 January 2026" or "15th January, 2026")
    (r'(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(MONTH_MAP.keys()) + r')[,.]?\s+(\d{4})', 'dmy_text'),
    # Month DD, YYYY (e.g., "January 15, 2026")
    (r'(' + '|'.join(MONTH_MAP.keys()) + r')\s+(\d{1,2})(?:st|nd|rd|th)?[,.]?\s+(\d{4})', 'mdy_text'),
    # Month YYYY (e.g., "January 2026") - day defaults to 1
    (r'(' + '|'.join(MONTH_MAP.keys()) + r')[,.]?\s+(\d{4})', 'my_text'),
]

# Keywords indicating a last/closing date
LAST_DATE_KEYWORDS = [
    "last date", "closing date", "deadline", "apply before", "apply by",
    "last day", "due date", "submission date", "end date", "expires",
    "last date of", "last date for", "on or before", "not later than",
    "upto", "up to", "extended till", "extended to", "extended up to",
    "close on", "closes on", "last date to apply",
]

# Keywords indicating a posting/notification date
POSTED_DATE_KEYWORDS = [
    "posted on", "dated", "published", "notification date", "date of notification",
    "advertisement date", "advt date", "issued on", "published on", "date of publication",
    "date of advertisement", "notified on", "date of issue",
]


def parse_date_string(date_str, fmt_type):
    """Parse a date string based on format type. Returns a date object or None."""
    try:
        if fmt_type == 'dmy_numeric':
            m = re.match(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', date_str)
            if m:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100:
                    return datetime(y, mo, d).date()
        elif fmt_type == 'ymd_numeric':
            m = re.match(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', date_str)
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100:
                    return datetime(y, mo, d).date()
        elif fmt_type == 'dmy_text':
            m = re.match(
                r'(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(MONTH_MAP.keys()) + r')[,.]?\s+(\d{4})',
                date_str, re.IGNORECASE
            )
            if m:
                d = int(m.group(1))
                mo = MONTH_MAP[m.group(2).lower()]
                y = int(m.group(3))
                if 1 <= d <= 31 and 1900 <= y <= 2100:
                    return datetime(y, mo, d).date()
        elif fmt_type == 'mdy_text':
            m = re.match(
                r'(' + '|'.join(MONTH_MAP.keys()) + r')\s+(\d{1,2})(?:st|nd|rd|th)?[,.]?\s+(\d{4})',
                date_str, re.IGNORECASE
            )
            if m:
                mo = MONTH_MAP[m.group(1).lower()]
                d = int(m.group(2))
                y = int(m.group(3))
                if 1 <= d <= 31 and 1900 <= y <= 2100:
                    return datetime(y, mo, d).date()
        elif fmt_type == 'my_text':
            m = re.match(
                r'(' + '|'.join(MONTH_MAP.keys()) + r')[,.]?\s+(\d{4})',
                date_str, re.IGNORECASE
            )
            if m:
                mo = MONTH_MAP[m.group(1).lower()]
                y = int(m.group(2))
                if 1900 <= y <= 2100:
                    return datetime(y, mo, 1).date()
    except (ValueError, OverflowError):
        pass
    return None


def extract_all_dates(text):
    """Extract all dates from a text string. Returns list of (date_obj, match_start_pos)."""
    dates_found = []
    if not text:
        return dates_found
    for pattern, fmt_type in DATE_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            parsed = parse_date_string(m.group(0), fmt_type)
            if parsed:
                dates_found.append((parsed, m.start()))
    return dates_found


def classify_dates(text, dates_found):
    """
    Given text and a list of (date, position) tuples, classify each date
    as 'posted_date' or 'last_date' based on nearby keywords.

    Returns (posted_date, last_date) as date objects or None.
    """
    posted_date = None
    last_date = None
    text_lower = text.lower()

    for date_obj, pos in dates_found:
        # Look at surrounding text (200 chars before the date match)
        context_start = max(0, pos - 200)
        context = text_lower[context_start:pos + 50]

        is_last = any(kw in context for kw in LAST_DATE_KEYWORDS)
        is_posted = any(kw in context for kw in POSTED_DATE_KEYWORDS)

        if is_last:
            # Prefer latest last_date if multiple found
            if last_date is None or date_obj > last_date:
                last_date = date_obj
        elif is_posted:
            if posted_date is None or date_obj > posted_date:
                posted_date = date_obj

    # If we have dates but couldn't classify them via keywords, use heuristics
    if dates_found and not posted_date and not last_date:
        all_dates = sorted(set(d for d, _ in dates_found))
        if len(all_dates) == 1:
            # Single date - if in the future, likely a deadline; if past, likely posted date
            if all_dates[0] >= TODAY:
                last_date = all_dates[0]
            else:
                posted_date = all_dates[0]
        elif len(all_dates) >= 2:
            # Multiple dates - earliest is likely posted, latest is likely last date
            posted_date = all_dates[0]
            last_date = all_dates[-1]

    return posted_date, last_date


def get_surrounding_text(link_element, soup=None):
    """
    Get text surrounding a link element for date extraction.
    Looks at the parent element, sibling elements, and nearby table cells/rows.
    """
    texts = []

    # The link's own text
    texts.append(link_element.get_text(strip=True))

    # Parent element text
    parent = link_element.parent
    if parent and isinstance(parent, Tag):
        texts.append(parent.get_text(" ", strip=True))

        # Grandparent (often a <td>, <li>, <div>)
        grandparent = parent.parent
        if grandparent and isinstance(grandparent, Tag):
            texts.append(grandparent.get_text(" ", strip=True))

            # If in a table row, get the entire row text
            if grandparent.name == 'tr':
                texts.append(grandparent.get_text(" ", strip=True))
            elif grandparent.name == 'td':
                row = grandparent.parent
                if row and isinstance(row, Tag) and row.name == 'tr':
                    texts.append(row.get_text(" ", strip=True))

    # Previous and next siblings
    for sibling in [link_element.previous_sibling, link_element.next_sibling]:
        if sibling and isinstance(sibling, Tag):
            texts.append(sibling.get_text(" ", strip=True))
        elif sibling and isinstance(sibling, str):
            texts.append(sibling.strip())

    # Also check previous and next sibling elements of parent
    if parent and isinstance(parent, Tag):
        prev_sib = parent.find_previous_sibling()
        next_sib = parent.find_next_sibling()
        if prev_sib and isinstance(prev_sib, Tag):
            texts.append(prev_sib.get_text(" ", strip=True))
        if next_sib and isinstance(next_sib, Tag):
            texts.append(next_sib.get_text(" ", strip=True))

    combined = " ".join(t for t in texts if t)
    return combined


def extract_dates_for_link(link_element, title_text=""):
    """
    Extract posted_date and last_date for a given link element.
    Returns (posted_date_str, last_date_str) as ISO format strings or None.
    """
    surrounding = get_surrounding_text(link_element)

    # Also try to extract from the title itself
    full_text = f"{title_text} {surrounding}"

    dates_found = extract_all_dates(full_text)
    posted_date, last_date = classify_dates(full_text, dates_found)

    posted_str = posted_date.isoformat() if posted_date else None
    last_str = last_date.isoformat() if last_date else None

    return posted_str, last_str


# ============================================================
# DEEP SCRAPE INFRASTRUCTURE
# ============================================================

# Cache for deep scrape results to avoid re-fetching the same URL
_deep_scrape_cache = {}
# Timestamp of last deep-scrape request for rate limiting
_deep_scrape_last_request = 0.0
DEEP_SCRAPE_DELAY = 0.5  # seconds between requests
DEEP_SCRAPE_MAX_PER_SOURCE = 10  # max links to follow per scraper function


def _rate_limit():
    """Enforce a minimum delay between deep-scrape HTTP requests."""
    global _deep_scrape_last_request
    now = time.time()
    elapsed = now - _deep_scrape_last_request
    if elapsed < DEEP_SCRAPE_DELAY:
        time.sleep(DEEP_SCRAPE_DELAY - elapsed)
    _deep_scrape_last_request = time.time()


def deep_scrape(url, label, verify_ssl=True):
    """
    Follow a link to its detail/notification page and extract:
    - full_title: the page <title> or main heading
    - apply_url: the best actionable link found (application portal > circular PDF > gazette PDF > any PDF)
    - pdf_url: any PDF link found on the page (the actual vacancy circular)
    - posted_date: notification/posted date found via keyword matching
    - last_date: last date to apply found via keyword matching
    - detail_url: the URL that was fetched

    Returns a dict with these keys, or an empty dict on failure.
    All values default to None if not found.

    Priority for apply_url:
      1. Application portal links (upsconline, external form URLs, etc.)
      2. "Apply Now" / "Click Here to Apply" links found in the page
      3. Vacancy circular PDF (with keywords like vacancy, notification, advt)
      4. Gazette notification PDF
      5. Any PDF found on the page
      6. The detail page itself (fallback)
    """
    if not url:
        return {}

    # Normalize URL
    url = url.strip()

    # Check cache
    if url in _deep_scrape_cache:
        return _deep_scrape_cache[url]

    result = {
        "detail_url": url,
        "apply_url": None,
        "pdf_url": None,
        "posted_date": None,
        "last_date": None,
        "full_title": None,
    }

    # Skip URLs that are already PDFs - that IS the apply_url directly
    if url.lower().endswith(".pdf"):
        result["pdf_url"] = url
        result["apply_url"] = url
        log(f"    Deep-scrape: {label} -> direct PDF link (skipping fetch)")
        _deep_scrape_cache[url] = result
        return result

    try:
        _rate_limit()
        log(f"    Deep-scraping: {label} ({url[:80]}...)")
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=verify_ssl)
        resp.raise_for_status()
    except Exception as e:
        if verify_ssl and "SSL" in str(e).upper():
            try:
                resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
                resp.raise_for_status()
            except Exception as e2:
                log(f"    Deep-scrape failed for {url[:60]}: {e2}")
                _deep_scrape_cache[url] = result
                return result
        else:
            log(f"    Deep-scrape failed for {url[:60]}: {e}")
            _deep_scrape_cache[url] = result
            return result

    try:
        soup = BeautifulSoup(resp.text, "lxml")
        page_text = soup.get_text(" ", strip=True)

        # --- Extract full title ---
        title_tag = soup.find("title")
        if title_tag:
            result["full_title"] = title_tag.get_text(strip=True)[:300]

        # Also try h1/h2 for a better title
        for heading_tag in ["h1", "h2"]:
            h = soup.find(heading_tag)
            if h:
                heading_text = h.get_text(strip=True)
                if heading_text and len(heading_text) > 10:
                    result["full_title"] = heading_text[:300]
                    break

        # --- Collect all links with their text and href ---
        # Skip sidebar/navigation links by checking for common sidebar CSS classes
        sidebar_classes = {"discover-job-card", "sidebar", "widget", "nav-link",
                           "footer-link", "breadcrumb-link", "pagination-link"}
        all_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            # Skip links whose own CSS class is a known sidebar/widget class
            own_classes = set(a.get("class", []))
            if own_classes & sidebar_classes:
                continue
            link_text = a.get_text(strip=True).lower()
            full_href = href if href.startswith("http") else urljoin(url, href)
            all_links.append((link_text, full_href, a))

        # --- Category 1: Application portal links ---
        # These are links to known external application portals (highest priority)
        application_portal_links = []
        # Only match specific known government application portal domains
        portal_domains = [
            "upsconline.gov.in", "upsconline.nic.in", "apptrbmembermca.gov.in",
            "onlineapply", "nats.education.gov.in", "apprenticeshipindia.gov.in",
        ]
        for link_text, full_href, _ in all_links:
            href_lower = full_href.lower()
            # Check if the link points to a known application portal domain
            if any(domain in href_lower for domain in portal_domains):
                application_portal_links.append(full_href)

        # --- Category 2: "Apply Now" / "Click Here to Apply" / "Apply Online" links ---
        # Prioritize links that go to external domains (more likely to be actual application portals)
        from urllib.parse import urlparse
        page_domain = urlparse(url).netloc.lower()
        apply_action_links_external = []
        apply_action_links_internal = []
        apply_keywords = [
            "apply now", "apply online", "click here to apply", "apply here",
            "online application", "submit application", "apply for", "application form",
            "click here to download", "download application",
            "click here",
        ]
        for link_text, full_href, _ in all_links:
            if any(kw in link_text for kw in apply_keywords):
                link_domain = urlparse(full_href).netloc.lower()
                if link_domain != page_domain:
                    apply_action_links_external.append(full_href)
                else:
                    apply_action_links_internal.append(full_href)
        # External links first (they're actual application portals), then internal
        apply_action_links = apply_action_links_external + apply_action_links_internal

        # --- Category 3: Official notification / download links ---
        notification_links = []
        notification_keywords = [
            "official notification", "download notification", "notification pdf",
            "advertisement", "advt", "circular", "gazette",
            "download", "view notification", "detailed notification",
        ]
        for link_text, full_href, _ in all_links:
            if any(kw in link_text for kw in notification_keywords):
                notification_links.append(full_href)

        # --- Category 4: PDF links with vacancy-related keywords ---
        pdf_links = []
        vacancy_pdf_links = []
        gazette_pdf_links = []
        vacancy_pdf_keywords = [
            "vacancy", "circular", "notification", "recruit", "advt",
            "advertisement", "appointment", "selection",
        ]
        gazette_keywords = ["gazette", "rajpatra", "extraordinary"]

        for link_text, full_href, _ in all_links:
            if full_href.lower().endswith(".pdf") or ".pdf" in full_href.lower().split("?")[0]:
                pdf_links.append(full_href)
                combined = (link_text + " " + full_href).lower()
                if any(kw in combined for kw in vacancy_pdf_keywords):
                    vacancy_pdf_links.append(full_href)
                if any(kw in combined for kw in gazette_keywords):
                    gazette_pdf_links.append(full_href)

        # Also check embed/object/iframe sources for PDFs
        for tag_name in ["embed", "object", "iframe"]:
            for tag in soup.find_all(tag_name):
                src = tag.get("src") or tag.get("data") or ""
                if src and (".pdf" in src.lower()):
                    pdf_full = src if src.startswith("http") else urljoin(url, src)
                    pdf_links.append(pdf_full)

        # --- Determine the best apply_url by priority ---
        chosen_apply_url = None
        chosen_reason = None

        if application_portal_links:
            chosen_apply_url = application_portal_links[0]
            chosen_reason = "application portal link"
        elif apply_action_links:
            chosen_apply_url = apply_action_links[0]
            chosen_reason = "apply action link (Apply Now / Click Here)"
        elif vacancy_pdf_links:
            chosen_apply_url = vacancy_pdf_links[0]
            chosen_reason = "vacancy-related PDF"
        elif notification_links:
            # Prefer PDF notification links over HTML ones
            pdf_notif = [n for n in notification_links if ".pdf" in n.lower()]
            chosen_apply_url = pdf_notif[0] if pdf_notif else notification_links[0]
            chosen_reason = "official notification link"
        elif gazette_pdf_links:
            chosen_apply_url = gazette_pdf_links[0]
            chosen_reason = "gazette notification PDF"
        elif pdf_links:
            chosen_apply_url = pdf_links[0]
            chosen_reason = "PDF link (generic)"

        if chosen_apply_url:
            result["apply_url"] = chosen_apply_url
            log(f"    -> Found apply_url ({chosen_reason}): {chosen_apply_url[:100]}")

        # Keep pdf_url for backward compatibility
        if vacancy_pdf_links:
            result["pdf_url"] = vacancy_pdf_links[0]
        elif gazette_pdf_links:
            result["pdf_url"] = gazette_pdf_links[0]
        elif pdf_links:
            result["pdf_url"] = pdf_links[0]

        # --- Extract dates from the full page text ---
        dates_found = extract_all_dates(page_text)
        posted_date, last_date = classify_dates(page_text, dates_found)
        if posted_date:
            result["posted_date"] = posted_date.isoformat()
        if last_date:
            result["last_date"] = last_date.isoformat()

    except Exception as e:
        log(f"    Deep-scrape parse error for {url[:60]}: {e}")

    _deep_scrape_cache[url] = result
    return result


def enrich_vacancy(vacancy, deep_info):
    """
    Merge deep-scrape results into a vacancy dict.
    Only overwrites fields if the deep scrape found better data.
    Does not remove existing data.
    """
    if not deep_info:
        return vacancy

    # Set apply_url: prefer the deep-scraped apply_url, then pdf_url, then existing
    if deep_info.get("apply_url"):
        vacancy["apply_url"] = deep_info["apply_url"]
    elif deep_info.get("pdf_url") and not vacancy.get("apply_url"):
        vacancy["apply_url"] = deep_info["pdf_url"]
    if deep_info.get("detail_url"):
        vacancy["detail_url"] = deep_info["detail_url"]

    # Use deep-scraped dates only if better than what we have
    if deep_info.get("last_date") and not vacancy.get("last_date"):
        vacancy["last_date"] = deep_info["last_date"]
        vacancy["status"] = compute_status(deep_info["last_date"])
    elif deep_info.get("last_date") and vacancy.get("last_date"):
        # Prefer the deep-scraped date as it comes from the actual notification
        vacancy["last_date"] = deep_info["last_date"]
        vacancy["status"] = compute_status(deep_info["last_date"])

    if deep_info.get("posted_date") and not vacancy.get("posted_date"):
        vacancy["posted_date"] = deep_info["posted_date"]

    # Upgrade title if deep scrape found a better one
    if deep_info.get("full_title") and len(deep_info["full_title"]) > len(vacancy.get("title", "")):
        vacancy["title"] = deep_info["full_title"][:300]

    return vacancy


def compute_status(last_date_str):
    """Compute vacancy status based on last_date."""
    if not last_date_str:
        return "active"  # Unknown deadline treated as active
    try:
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
        if last_date < TODAY:
            return "expired"
        else:
            return "active"
    except (ValueError, TypeError):
        return "active"


def sort_vacancies(vacancies):
    """
    Sort vacancies by relevance:
    1. Active with known last_date (soonest deadline first)
    2. Active with unknown dates
    3. Expired (most recently expired first)
    """
    def sort_key(v):
        status = v.get("status", "active")
        last_date_str = v.get("last_date")

        if status == "active" and last_date_str:
            # Group 0: active with known deadline - sort by soonest first
            try:
                days_until = (datetime.strptime(last_date_str, "%Y-%m-%d").date() - TODAY).days
            except ValueError:
                days_until = 9999
            return (0, days_until)
        elif status == "active":
            # Group 1: active with no deadline
            return (1, 0)
        else:
            # Group 2: expired - most recently expired first
            if last_date_str:
                try:
                    days_since = (TODAY - datetime.strptime(last_date_str, "%Y-%m-%d").date()).days
                except ValueError:
                    days_since = 9999
                return (2, days_since)
            return (2, 9999)

    return sorted(vacancies, key=sort_key)


def generate_summary(vacancies):
    """Generate a summary section for the output."""
    active_count = sum(1 for v in vacancies if v.get("status") == "active")
    expired_count = sum(1 for v in vacancies if v.get("status") == "expired")

    # Upcoming deadlines: active vacancies with last_date within next 30 days
    upcoming_deadlines = []
    cutoff = TODAY + timedelta(days=30)
    for v in vacancies:
        if v.get("status") != "active" or not v.get("last_date"):
            continue
        try:
            ld = datetime.strptime(v["last_date"], "%Y-%m-%d").date()
            if TODAY <= ld <= cutoff:
                upcoming_deadlines.append({
                    "title": v["title"],
                    "source": v["source"],
                    "last_date": v["last_date"],
                    "days_remaining": (ld - TODAY).days,
                    "url": v["url"],
                })
        except (ValueError, TypeError):
            continue

    # Sort upcoming by days remaining
    upcoming_deadlines.sort(key=lambda x: x["days_remaining"])

    return {
        "active_count": active_count,
        "expired_count": expired_count,
        "total_count": len(vacancies),
        "upcoming_deadlines": upcoming_deadlines,
    }


# ============================================================
# 1. DEPT OF LEGAL AFFAIRS - VACANCY CIRCULARS
# ============================================================
def scrape_legal_affairs():
    soup, ok = safe_fetch("https://legalaffairs.gov.in/vacancy-circulars", "Dept of Legal Affairs - Vacancy Circulars")
    if not ok:
        return

    links = soup.find_all("a")
    count = 0
    deep_count = 0
    for link in links:
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if not text or len(text) < 10:
            continue
        keywords = ["vacancy", "circular", "member", "judicial", "tribunal", "selection", "appointment", "presiding"]
        if any(kw in text.lower() for kw in keywords):
            full_url = href if href.startswith("http") else f"https://legalaffairs.gov.in{href}"
            posted_date, last_date = extract_dates_for_link(link, text)
            status = compute_status(last_date)
            vacancy = {
                "source": "Dept of Legal Affairs",
                "title": text[:200],
                "url": full_url,
                "apply_url": None,
                "detail_url": None,
                "category": "Central Tribunal",
                "type": "vacancy_circular",
                "posted_date": posted_date,
                "last_date": last_date,
                "status": status,
                "scraped_at": datetime.now().isoformat()
            }

            # Deep scrape: follow link to get PDF URL and exact dates
            # Legal affairs often links directly to PDFs or pages with PDF links
            if deep_count < DEEP_SCRAPE_MAX_PER_SOURCE:
                deep_info = deep_scrape(full_url, f"Legal Affairs: {text[:50]}")
                vacancy = enrich_vacancy(vacancy, deep_info)
                deep_count += 1

            add_vacancy(vacancy)
            count += 1
    log(f"  Found {count} vacancy circulars ({deep_count} deep-scraped)")


# ============================================================
# 2. DEPT OF JUSTICE - VACANCY POSITIONS
# ============================================================
def scrape_doj():
    soup, ok = safe_fetch("https://doj.gov.in/vacancy-position/", "Dept of Justice - Vacancy Positions")
    if not ok:
        return

    links = soup.find_all("a")
    count = 0
    for link in links:
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if not text or len(text) < 10:
            continue
        keywords = ["vacancy", "judicial", "judge", "tribunal", "member", "appointment"]
        if any(kw in text.lower() for kw in keywords):
            full_url = href if href.startswith("http") else f"https://doj.gov.in{href}"
            posted_date, last_date = extract_dates_for_link(link, text)
            status = compute_status(last_date)
            add_vacancy({
                "source": "Dept of Justice",
                "title": text[:200],
                "url": full_url,
                "apply_url": None,
                "detail_url": None,
                "category": "Central Government",
                "type": "judicial_vacancy",
                "posted_date": posted_date,
                "last_date": last_date,
                "status": status,
                "scraped_at": datetime.now().isoformat()
            })
            count += 1
    log(f"  Found {count} DOJ vacancy items")


# ============================================================
# 3. LIVELAW JOB UPDATES (RSS-like page scraping)
# ============================================================
def scrape_livelaw():
    soup, ok = safe_fetch("https://www.livelaw.in/job-updates", "LiveLaw Job Updates")
    if not ok:
        return

    count = 0
    deep_count = 0

    # Search all links with job-related text
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if not text or len(text) < 15:
            continue
        keywords = ["judicial member", "member judicial", "tribunal", "vacancy", "presiding officer",
                     "consumer commission", "rera", "information commissioner", "lokayukta",
                     "human rights", "nclt", "nclat", "ncdrc", "cat ", "ngt ", "itat"]
        if any(kw in text.lower() for kw in keywords):
            full_url = href if href.startswith("http") else f"https://www.livelaw.in{href}"
            posted_date, last_date = extract_dates_for_link(link, text)
            status = compute_status(last_date)
            vacancy = {
                "source": "LiveLaw",
                "title": text[:200],
                "url": full_url,
                "apply_url": None,
                "detail_url": None,
                "category": "Job Update",
                "type": "livelaw_alert",
                "posted_date": posted_date,
                "last_date": last_date,
                "status": status,
                "scraped_at": datetime.now().isoformat()
            }

            # Deep scrape: LiveLaw articles contain full details
            # including organization name, position, last date, and apply links
            if deep_count < DEEP_SCRAPE_MAX_PER_SOURCE:
                deep_info = deep_scrape(full_url, f"LiveLaw: {text[:50]}")
                vacancy = enrich_vacancy(vacancy, deep_info)
                deep_count += 1

            add_vacancy(vacancy)
            count += 1
            if count >= 30:
                break
    log(f"  Found {count} LiveLaw job posts ({deep_count} deep-scraped)")


# ============================================================
# 4. NCLT / NCLAT
# ============================================================
def scrape_nclt():
    soup, ok = safe_fetch("https://nclt.gov.in/job-openings", "NCLT Job Openings")
    if not ok:
        return
    count = 0
    deep_count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["member", "judicial", "vacancy", "recruitment", "appointment", "circular"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://nclt.gov.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                vacancy = {
                    "source": "NCLT",
                    "title": text[:200],
                    "url": full_url,
                    "apply_url": None,
                    "detail_url": None,
                    "category": "Central Tribunal",
                    "type": "nclt",
                    "posted_date": posted_date,
                    "last_date": last_date,
                    "status": status,
                    "scraped_at": datetime.now().isoformat()
                }

                # Deep scrape to find actual notification/PDF
                if deep_count < DEEP_SCRAPE_MAX_PER_SOURCE:
                    deep_info = deep_scrape(full_url, f"NCLT: {text[:50]}")
                    vacancy = enrich_vacancy(vacancy, deep_info)
                    deep_count += 1

                add_vacancy(vacancy)
                count += 1
    log(f"  Found {count} NCLT items ({deep_count} deep-scraped)")


def scrape_nclat():
    soup, ok = safe_fetch("https://nclat.nic.in/recruitment", "NCLAT Recruitment")
    if not ok:
        return
    count = 0
    deep_count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["member", "judicial", "vacancy", "recruitment", "circular", "selection", "appointment"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://nclat.nic.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                vacancy = {
                    "source": "NCLAT",
                    "title": text[:200],
                    "url": full_url,
                    "apply_url": None,
                    "detail_url": None,
                    "category": "Central Tribunal",
                    "type": "nclat",
                    "posted_date": posted_date,
                    "last_date": last_date,
                    "status": status,
                    "scraped_at": datetime.now().isoformat()
                }

                # Deep scrape to find actual notification/PDF
                if deep_count < DEEP_SCRAPE_MAX_PER_SOURCE:
                    deep_info = deep_scrape(full_url, f"NCLAT: {text[:50]}")
                    vacancy = enrich_vacancy(vacancy, deep_info)
                    deep_count += 1

                add_vacancy(vacancy)
                count += 1
    log(f"  Found {count} NCLAT items ({deep_count} deep-scraped)")


# ============================================================
# 5. NCDRC
# ============================================================
def scrape_ncdrc():
    soup, ok = safe_fetch("https://ncdrc.nic.in/careers.html", "NCDRC Careers")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            full_url = href if href.startswith("http") else f"https://ncdrc.nic.in/{href}"
            posted_date, last_date = extract_dates_for_link(link, text)
            status = compute_status(last_date)
            add_vacancy({
                "source": "NCDRC",
                "title": text[:200],
                "url": full_url,
                "apply_url": None,
                "detail_url": None,
                "category": "Consumer Commission",
                "type": "ncdrc",
                "posted_date": posted_date,
                "last_date": last_date,
                "status": status,
                "scraped_at": datetime.now().isoformat()
            })
            count += 1
    log(f"  Found {count} NCDRC items")


# ============================================================
# 6. NHRC
# ============================================================
def scrape_nhrc():
    soup, ok = safe_fetch("https://nhrc.nic.in/activities/vacancies-results", "NHRC Vacancies")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "circular", "member", "appointment", "deputation"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://nhrc.nic.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({
                    "source": "NHRC",
                    "title": text[:200],
                    "url": full_url,
                    "apply_url": None,
                    "detail_url": None,
                    "category": "Commission",
                    "type": "nhrc",
                    "posted_date": posted_date,
                    "last_date": last_date,
                    "status": status,
                    "scraped_at": datetime.now().isoformat()
                })
                count += 1
    log(f"  Found {count} NHRC items")


# ============================================================
# 7. MINISTRY OF LABOUR
# ============================================================
def scrape_labour():
    soup, ok = safe_fetch("https://labour.gov.in/", "Ministry of Labour")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["presiding officer", "tribunal", "labour court", "vacancy", "circular"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://labour.gov.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({
                    "source": "Ministry of Labour",
                    "title": text[:200],
                    "url": full_url,
                    "apply_url": None,
                    "detail_url": None,
                    "category": "Industrial Tribunal",
                    "type": "labour_tribunal",
                    "posted_date": posted_date,
                    "last_date": last_date,
                    "status": status,
                    "scraped_at": datetime.now().isoformat()
                })
                count += 1
    log(f"  Found {count} Labour Ministry items")


# ============================================================
# 8. ALLAHABAD HC - TRIBUNAL VACANCIES
# ============================================================
def scrape_allahabad_hc():
    soup, ok = safe_fetch("https://www.allahabadhighcourt.in/misc/tribunal_vacancy.html", "Allahabad HC - Tribunal Vacancies")
    if not ok:
        return
    count = 0
    deep_count = 0
    base_url = "https://www.allahabadhighcourt.in"
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            # Allahabad HC uses onclick="location.href='/event/event_XXXXX.pdf'" instead of href
            # Extract the actual URL from onclick if href is empty
            onclick = link.get("onclick", "")
            onclick_url = ""
            if onclick:
                m = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
                if m:
                    onclick_url = m.group(1)

            # Determine the actual URL: prefer href, fallback to onclick
            if href:
                full_url = href if href.startswith("http") else urljoin(base_url + "/misc/", href)
            elif onclick_url:
                full_url = onclick_url if onclick_url.startswith("http") else urljoin(base_url, onclick_url)
            else:
                continue  # No usable URL

            posted_date, last_date = extract_dates_for_link(link, text)
            status = compute_status(last_date)

            # Determine apply_url directly for PDF links
            # Most Allahabad HC links are direct PDF vacancy circulars (via onclick)
            apply_url = None
            effective_href = href or onclick_url
            if effective_href.lower().endswith(".pdf"):
                apply_url = full_url
                log(f"    Allahabad HC -> direct PDF as apply_url: {full_url[:80]}")

            vacancy = {
                "source": "Allahabad HC",
                "title": text[:200],
                "url": full_url,
                "apply_url": apply_url,
                "detail_url": full_url if apply_url else None,
                "category": "Tribunal Vacancy",
                "type": "high_court",
                "posted_date": posted_date,
                "last_date": last_date,
                "status": status,
                "scraped_at": datetime.now().isoformat()
            }

            # Deep scrape non-PDF links to find actual PDF circulars
            if not apply_url and deep_count < DEEP_SCRAPE_MAX_PER_SOURCE:
                deep_info = deep_scrape(full_url, f"Allahabad HC: {text[:50]}", verify_ssl=False)
                vacancy = enrich_vacancy(vacancy, deep_info)
                deep_count += 1

            add_vacancy(vacancy)
            count += 1
    log(f"  Found {count} Allahabad HC items ({deep_count} deep-scraped)")


# ============================================================
# 9. ITAT
# ============================================================
def scrape_itat():
    soup, ok = safe_fetch("https://itat.gov.in/", "ITAT")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            keywords = ["recruitment", "vacancy", "member", "judicial", "appointment", "circular"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://itat.gov.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({
                    "source": "ITAT",
                    "title": text[:200],
                    "url": full_url,
                    "apply_url": None,
                    "detail_url": None,
                    "category": "Central Tribunal",
                    "type": "itat",
                    "posted_date": posted_date,
                    "last_date": last_date,
                    "status": status,
                    "scraped_at": datetime.now().isoformat()
                })
                count += 1
    log(f"  Found {count} ITAT items")


# ============================================================
# 10. GSTAT
# ============================================================
def scrape_gstat():
    soup, ok = safe_fetch("https://dor.gov.in/gstat-recruitment", "GSTAT Recruitment")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            keywords = ["recruitment", "vacancy", "member", "judicial", "appointment", "gstat"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://dor.gov.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({
                    "source": "GSTAT",
                    "title": text[:200],
                    "url": full_url,
                    "apply_url": None,
                    "detail_url": None,
                    "category": "Central Tribunal",
                    "type": "gstat",
                    "posted_date": posted_date,
                    "last_date": last_date,
                    "status": status,
                    "scraped_at": datetime.now().isoformat()
                })
                count += 1
    log(f"  Found {count} GSTAT items")


# ============================================================
# 11. CERC
# ============================================================
def scrape_cerc():
    soup, ok = safe_fetch("https://www.cercind.gov.in/vacancy.html", "CERC Vacancies", verify=False)
    if not ok:
        soup, ok = safe_fetch("https://cercind.gov.in/vacancy.html", "CERC Vacancies (alt)", verify=False)
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            full_url = href if href.startswith("http") else f"https://www.cercind.gov.in/{href}"
            posted_date, last_date = extract_dates_for_link(link, text)
            status = compute_status(last_date)
            add_vacancy({
                "source": "CERC",
                "title": text[:200],
                "url": full_url,
                "apply_url": None,
                "detail_url": None,
                "category": "Electricity Commission",
                "type": "cerc",
                "posted_date": posted_date,
                "last_date": last_date,
                "status": status,
                "scraped_at": datetime.now().isoformat()
            })
            count += 1
    log(f"  Found {count} CERC items")


# ============================================================
# 12. GOVT JOB GURU - JUDICIAL JOBS
# ============================================================
def scrape_govtjobguru():
    soup, ok = safe_fetch("https://govtjobguru.in/govt-jobs-by-department/judicial-jobs/", "GovtJobGuru Judicial Jobs")
    if not ok:
        return
    count = 0
    deep_count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 15:
            keywords = ["judicial", "member", "tribunal", "commission", "judge", "presiding",
                         "consumer", "rera", "vacancy", "recruitment"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://govtjobguru.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                vacancy = {
                    "source": "GovtJobGuru",
                    "title": text[:200],
                    "url": full_url,
                    "apply_url": None,
                    "detail_url": None,
                    "category": "Job Aggregator",
                    "type": "aggregator",
                    "posted_date": posted_date,
                    "last_date": last_date,
                    "status": status,
                    "scraped_at": datetime.now().isoformat()
                }

                # Deep scrape: GovtJobGuru articles have "Apply Online" buttons
                if deep_count < DEEP_SCRAPE_MAX_PER_SOURCE:
                    deep_info = deep_scrape(full_url, f"GovtJobGuru: {text[:50]}")
                    vacancy = enrich_vacancy(vacancy, deep_info)
                    deep_count += 1

                add_vacancy(vacancy)
                count += 1
                if count >= 20:
                    break
    log(f"  Found {count} GovtJobGuru items ({deep_count} deep-scraped)")


# ============================================================
# 13. MCA PORTAL - NCLT/NCLAT MEMBER APPOINTMENT
# ============================================================
def scrape_mca():
    mca_portal_url = "https://apptrbmembermca.gov.in/"
    soup, ok = safe_fetch(mca_portal_url, "MCA Tribunal Member Portal")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 5:
            full_url = href if href.startswith("http") else f"https://apptrbmembermca.gov.in/{href}"
            posted_date, last_date = extract_dates_for_link(link, text)
            status = compute_status(last_date)
            # MCA Portal IS the application portal itself for NCLT/NCLAT member appointments
            # So the apply_url should point to the portal or the specific link
            apply_url = full_url
            # If the link itself points to a PDF, that's the notification; portal is still the apply target
            if full_url.lower().endswith(".pdf"):
                apply_url = full_url  # PDF is the notification/apply document
            elif "apply" in text.lower() or "register" in text.lower() or "login" in text.lower():
                apply_url = full_url  # Direct apply/register link
            else:
                apply_url = mca_portal_url  # Default to portal homepage as apply URL
            log(f"    MCA Portal -> apply_url: {apply_url[:80]}")
            add_vacancy({
                "source": "MCA Portal",
                "title": text[:200],
                "url": full_url,
                "apply_url": apply_url,
                "detail_url": full_url,
                "category": "Central Tribunal",
                "type": "mca_portal",
                "posted_date": posted_date,
                "last_date": last_date,
                "status": status,
                "scraped_at": datetime.now().isoformat()
            })
            count += 1
    log(f"  Found {count} MCA Portal items")


# ============================================================
# 14. UPSC
# ============================================================
def scrape_upsc():
    soup, ok = safe_fetch("https://www.upsc.gov.in/recruitment/vacancy-circulars", "UPSC Vacancy Circulars", verify=False)
    if not ok:
        soup, ok = safe_fetch("https://upsc.gov.in/recruitment/vacancy-circulars", "UPSC Vacancy Circulars (alt)", verify=False)
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["tribunal", "member", "judicial", "prosecutor", "legal", "law"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://www.upsc.gov.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({
                    "source": "UPSC",
                    "title": text[:200],
                    "url": full_url,
                    "apply_url": None,
                    "detail_url": None,
                    "category": "UPSC",
                    "type": "upsc",
                    "posted_date": posted_date,
                    "last_date": last_date,
                    "status": status,
                    "scraped_at": datetime.now().isoformat()
                })
                count += 1
    log(f"  Found {count} UPSC items")


# ============================================================
# 15. STATE RERA PORTALS
# ============================================================
def scrape_state_rera():
    rera_sites = [
        ("https://rera.ap.gov.in", "AP RERA"),
        ("https://rera.telangana.gov.in", "Telangana RERA"),
        ("https://mahareat.maharashtra.gov.in/", "Maharashtra RERA Tribunal"),
        ("https://haryanarera.gov.in", "Haryana RERA"),
        ("https://rera.punjab.gov.in/appellate-tribunal.html", "Punjab RERA"),
        ("https://rera.karnataka.gov.in/", "Karnataka RERA"),
        ("https://rera.rajasthan.gov.in/", "Rajasthan RERA"),
        ("https://rera.up.gov.in/", "UP RERA"),
        ("https://rera.tn.gov.in/", "Tamil Nadu RERA"),
        ("https://gujrera.gujarat.gov.in/", "Gujarat RERA"),
        ("https://maharera.maharashtra.gov.in/", "Maharashtra RERA"),
    ]
    for url, name in rera_sites:
        soup, ok = safe_fetch(url, name)
        if not ok:
            continue
        count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 10:
                keywords = ["vacancy", "recruitment", "member", "judicial", "appointment", "tribunal"]
                if any(kw in text.lower() for kw in keywords):
                    full_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
                    posted_date, last_date = extract_dates_for_link(link, text)
                    status = compute_status(last_date)
                    add_vacancy({
                        "source": name,
                        "title": text[:200],
                        "url": full_url,
                        "apply_url": None,
                        "detail_url": None,
                        "category": "State RERA",
                        "type": "rera",
                        "posted_date": posted_date,
                        "last_date": last_date,
                        "status": status,
                        "scraped_at": datetime.now().isoformat()
                    })
                    count += 1
        log(f"  Found {count} items from {name}")


# ============================================================
# 16. DRT / DRAT - DEBT RECOVERY TRIBUNALS
# ============================================================
def scrape_drt():
    soup, ok = safe_fetch("https://drt.gov.in/", "DRT Portal")
    if ok:
        count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 8:
                keywords = ["vacancy", "recruitment", "presiding", "chairperson", "appointment", "member"]
                if any(kw in text.lower() for kw in keywords):
                    full_url = href if href.startswith("http") else f"https://drt.gov.in/{href}"
                    posted_date, last_date = extract_dates_for_link(link, text)
                    status = compute_status(last_date)
                    add_vacancy({"source": "DRT/DRAT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Debt Recovery Tribunal", "type": "drt", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                    count += 1
        log(f"  Found {count} DRT items")

    soup2, ok2 = safe_fetch("https://financialservices.gov.in/beta/en/page/debts-recovery-tribunals-debts-recovery-appellate-tribunals", "DRT/DRAT - Ministry of Finance")
    if ok2:
        count = 0
        for link in soup2.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 8:
                keywords = ["vacancy", "recruitment", "presiding", "chairperson", "appointment", "drt", "drat"]
                if any(kw in text.lower() for kw in keywords):
                    full_url = href if href.startswith("http") else f"https://financialservices.gov.in{href}"
                    posted_date, last_date = extract_dates_for_link(link, text)
                    status = compute_status(last_date)
                    add_vacancy({"source": "Ministry of Finance - DRT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Debt Recovery Tribunal", "type": "drt", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                    count += 1
        log(f"  Found {count} Ministry of Finance DRT items")


# ============================================================
# 17. RAILWAY CLAIMS TRIBUNAL
# ============================================================
def scrape_rct():
    soup, ok = safe_fetch("https://rct.indianrail.gov.in/", "Railway Claims Tribunal", verify=False)
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            keywords = ["vacancy", "recruitment", "member", "judicial", "appointment"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://rct.indianrail.gov.in/{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Railway Claims Tribunal", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Central Tribunal", "type": "rct", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} RCT items")


# ============================================================
# 18. ARMED FORCES TRIBUNAL
# ============================================================
def scrape_aft():
    soup, ok = safe_fetch("https://aftdelhi.nic.in/index.php/vacancies", "Armed Forces Tribunal - Vacancies")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            full_url = href if href.startswith("http") else f"https://aftdelhi.nic.in/{href}"
            posted_date, last_date = extract_dates_for_link(link, text)
            status = compute_status(last_date)
            add_vacancy({"source": "Armed Forces Tribunal", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Central Tribunal", "type": "aft", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
            count += 1
    log(f"  Found {count} AFT items")


# ============================================================
# 19. APTEL - APPELLATE TRIBUNAL FOR ELECTRICITY
# ============================================================
def scrape_aptel():
    soup, ok = safe_fetch("https://www.aptel.gov.in/en", "APTEL")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            keywords = ["vacancy", "recruitment", "member", "judicial", "appointment", "career"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://www.aptel.gov.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "APTEL", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Electricity Tribunal", "type": "aptel", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} APTEL items")


# ============================================================
# 20. TDSAT - TELECOM DISPUTES TRIBUNAL
# ============================================================
def scrape_tdsat():
    soup, ok = safe_fetch("https://tdsat.gov.in/", "TDSAT")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            keywords = ["vacancy", "recruitment", "member", "judicial", "appointment"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://tdsat.gov.in/{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "TDSAT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Telecom Tribunal", "type": "tdsat", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} TDSAT items")


# ============================================================
# 21. SAT - SECURITIES APPELLATE TRIBUNAL
# ============================================================
def scrape_sat():
    soup, ok = safe_fetch("https://satweb.sat.gov.in/vacancy-circular", "SAT Vacancy Circulars")
    if not ok:
        soup, ok = safe_fetch("https://sat.gov.in/", "Securities Appellate Tribunal", verify=False)
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            keywords = ["vacancy", "recruitment", "member", "judicial", "appointment", "career"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://sat.gov.in/{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "SAT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Securities Tribunal", "type": "sat", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} SAT items")


# ============================================================
# 22. LOKPAL
# ============================================================
def scrape_lokpal():
    soup, ok = safe_fetch("https://lokpal.gov.in/", "Lokpal", verify=False)
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 8:
            keywords = ["vacancy", "recruitment", "member", "judicial", "appointment"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://lokpal.gov.in/{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Lokpal", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Anti-Corruption", "type": "lokpal", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} Lokpal items")


# ============================================================
# 23. ADDITIONAL HIGH COURTS - TRIBUNAL VACANCIES
# ============================================================
def scrape_high_courts():
    hc_sites = [
        ("https://tshc.gov.in", "Telangana HC"),
        ("https://hcmadras.tn.gov.in/vacancy.php", "Madras HC"),
        ("https://delhihighcourt.nic.in/web/job-openings", "Delhi HC"),
        ("https://ghconline.gov.in", "Gauhati HC"),
        ("https://jharkhandhighcourt.nic.in/vacancies-other-govt-deppt.php", "Jharkhand HC"),
    ]
    for url, name in hc_sites:
        soup, ok = safe_fetch(url, name)
        if not ok:
            continue
        count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 10:
                keywords = ["tribunal", "vacancy", "member", "judicial", "presiding", "appointment",
                            "circular", "recruitment", "commission"]
                if any(kw in text.lower() for kw in keywords):
                    full_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
                    posted_date, last_date = extract_dates_for_link(link, text)
                    status = compute_status(last_date)
                    add_vacancy({"source": name, "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "High Court - Tribunal Vacancy", "type": "high_court", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                    count += 1
        log(f"  Found {count} items from {name}")


# ============================================================
# 24. CONSUMER AFFAIRS - SCDRC / DCDRC
# ============================================================
def scrape_consumer_affairs():
    soup, ok = safe_fetch("https://consumeraffairs.nic.in/", "Ministry of Consumer Affairs")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "president", "member", "commission", "consumer", "appointment", "recruitment"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://consumeraffairs.nic.in/{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Consumer Affairs Ministry", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Consumer Commission", "type": "consumer", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} Consumer Affairs items")


# ============================================================
# 25. LIVELAW - ADDITIONAL TAGS
# ============================================================
def scrape_livelaw_tags():
    tags = [
        ("https://www.livelaw.in/tags/tribunal-vacancy", "LiveLaw - Tribunal Vacancy"),
        ("https://www.livelaw.in/tags/consumer-commission", "LiveLaw - Consumer Commission"),
        ("https://www.livelaw.in/tags/presiding-officer", "LiveLaw - Presiding Officer"),
    ]
    for url, name in tags:
        soup, ok = safe_fetch(url, name)
        if not ok:
            continue
        count = 0
        deep_count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 20 and "/job-updates/" in href:
                full_url = href if href.startswith("http") else f"https://www.livelaw.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                vacancy = {
                    "source": name,
                    "title": text[:200],
                    "url": full_url,
                    "apply_url": None,
                    "detail_url": None,
                    "category": "Job Update",
                    "type": "livelaw_tag",
                    "posted_date": posted_date,
                    "last_date": last_date,
                    "status": status,
                    "scraped_at": datetime.now().isoformat()
                }

                # Deep scrape LiveLaw articles for full details
                if deep_count < DEEP_SCRAPE_MAX_PER_SOURCE:
                    deep_info = deep_scrape(full_url, f"{name}: {text[:50]}")
                    vacancy = enrich_vacancy(vacancy, deep_info)
                    deep_count += 1

                add_vacancy(vacancy)
                count += 1
                if count >= 15:
                    break
        log(f"  Found {count} items from {name} ({deep_count} deep-scraped)")


# ============================================================
# 26. STATE ELECTRICITY REGULATORY COMMISSIONS
# ============================================================
def scrape_state_ercs():
    erc_sites = [
        ("https://www.derc.gov.in/", "Delhi ERC"),
        ("https://www.mperc.in", "MP ERC"),
        ("https://www.uperc.org/", "UP ERC"),
        ("https://www.cserc.gov.in/", "Chhattisgarh ERC"),
        ("https://rerc.rajasthan.gov.in/", "Rajasthan ERC"),
        ("https://herc.gov.in/", "Haryana ERC"),
        ("https://www.tnerc.gov.in/", "Tamil Nadu ERC"),
        ("https://www.aperc.gov.in/", "AP ERC"),
        ("https://www.kserc.org/", "Kerala ERC"),
    ]
    for url, name in erc_sites:
        soup, ok = safe_fetch(url, name)
        if not ok:
            continue
        count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 8:
                keywords = ["vacancy", "recruitment", "member", "law", "appointment", "ombudsman"]
                if any(kw in text.lower() for kw in keywords):
                    full_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
                    posted_date, last_date = extract_dates_for_link(link, text)
                    status = compute_status(last_date)
                    add_vacancy({"source": name, "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Electricity Commission", "type": "erc", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                    count += 1
        log(f"  Found {count} items from {name}")


# ============================================================
# 27. VERDICTUM (LEGAL JOB AGGREGATOR)
# ============================================================
def scrape_verdictum():
    soup, ok = safe_fetch("https://www.verdictum.in/job-updates", "Verdictum Job Updates")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 15:
            keywords = ["judicial member", "tribunal", "presiding officer", "commission", "member judicial",
                         "member law", "consumer", "rera", "information commissioner", "lokayukta"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else f"https://www.verdictum.in{href}"
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Verdictum", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Job Aggregator", "type": "verdictum", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
                if count >= 20:
                    break
    log(f"  Found {count} Verdictum items")


# ============================================================
# 28. NGT - NATIONAL GREEN TRIBUNAL
# ============================================================
def scrape_ngt():
    for url, label in [
        ("https://greentribunal.gov.in/public-notices/job-opening", "NGT Job Openings"),
        ("https://greentribunal.gov.in", "NGT Homepage"),
    ]:
        soup, ok = safe_fetch(url, label)
        if not ok:
            continue
        count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 10:
                keywords = ["vacancy", "recruitment", "member", "judicial", "expert", "appointment", "registrar", "job", "circular"]
                if any(kw in text.lower() for kw in keywords):
                    full_url = href if href.startswith("http") else urljoin("https://greentribunal.gov.in/", href)
                    posted_date, last_date = extract_dates_for_link(link, text)
                    status = compute_status(last_date)
                    add_vacancy({"source": "NGT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Green Tribunal", "type": "ngt", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                    count += 1
        log(f"  Found {count} NGT items from {label}")


# ============================================================
# 29. CAT - CENTRAL ADMINISTRATIVE TRIBUNAL
# ============================================================
def scrape_cat():
    cat_sites = [
        ("https://cgat.gov.in/", "Central Administrative Tribunal"),
        ("https://cis.cgat.gov.in/", "CAT CIS Portal"),
    ]
    for url, label in cat_sites:
        soup, ok = safe_fetch(url, label)
        if not ok:
            continue
        count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 10:
                keywords = ["vacancy", "recruitment", "member", "judicial", "appointment", "registrar", "circular"]
                if any(kw in text.lower() for kw in keywords):
                    full_url = href if href.startswith("http") else urljoin(url, href)
                    posted_date, last_date = extract_dates_for_link(link, text)
                    status = compute_status(last_date)
                    add_vacancy({"source": "CAT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Central Tribunal", "type": "cat", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                    count += 1
        log(f"  Found {count} CAT items from {label}")


# ============================================================
# 30. CESTAT - CUSTOMS EXCISE & SERVICE TAX APPELLATE TRIBUNAL
# ============================================================
def scrape_cestat():
    soup, ok = safe_fetch("https://cestat.gov.in/", "CESTAT")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "judicial", "appointment", "circular"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://cestat.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "CESTAT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Tax Tribunal", "type": "cestat", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} CESTAT items")


# ============================================================
# 31. CCI - COMPETITION COMMISSION OF INDIA
# ============================================================
def scrape_cci():
    soup, ok = safe_fetch("https://www.cci.gov.in/legal-framwork/notifications/list/appointment-of-chairperson-and-members", "CCI Appointments")
    if not ok:
        # Fallback to main recruitment page
        soup, ok = safe_fetch("https://www.cci.gov.in/en/recruitment", "CCI Recruitment")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "chairperson", "appointment", "selection", "legal"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://www.cci.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "CCI", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Competition Commission", "type": "cci", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} CCI items")


# ============================================================
# 32. IBBI - INSOLVENCY AND BANKRUPTCY BOARD OF INDIA
# ============================================================
def scrape_ibbi():
    soup, ok = safe_fetch("https://ibbi.gov.in/home/career", "IBBI Careers")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "appointment", "whole-time", "executive director", "legal"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://ibbi.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "IBBI", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Insolvency Board", "type": "ibbi", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} IBBI items")


# ============================================================
# 33. NALSA - NATIONAL LEGAL SERVICES AUTHORITY (LOK ADALAT)
# ============================================================
def scrape_nalsa():
    soup, ok = safe_fetch("https://nalsa.gov.in/", "NALSA")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "presiding", "appointment", "lok adalat", "chairperson", "permanent lok"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://nalsa.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "NALSA", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Legal Services", "type": "nalsa", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} NALSA items")


# ============================================================
# 34. LAW COMMISSION OF INDIA
# ============================================================
def scrape_law_commission():
    soup, ok = safe_fetch("https://lawcommissionofindia.nic.in/", "Law Commission of India")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "appointment", "consultant", "legal"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://lawcommissionofindia.nic.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Law Commission", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Law Commission", "type": "law_commission", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} Law Commission items")


# ============================================================
# 35. SEBI - SECURITIES AND EXCHANGE BOARD OF INDIA
# ============================================================
def scrape_sebi():
    soup, ok = safe_fetch("https://www.sebi.gov.in/department/human-resources-department-37/opportunity.html", "SEBI Opportunities")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "legal", "appointment", "officer", "whole-time"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://www.sebi.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "SEBI", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Securities Regulator", "type": "sebi", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} SEBI items")


# ============================================================
# 36. CGIT - CENTRAL GOVERNMENT INDUSTRIAL TRIBUNAL / LABOUR COURTS
# ============================================================
def scrape_cgit():
    soup, ok = safe_fetch("https://cgit.labour.gov.in/", "CGIT Labour Courts")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "presiding officer", "appointment", "judicial", "circular"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://cgit.labour.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "CGIT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Labour Tribunal", "type": "cgit", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} CGIT items")


# ============================================================
# 37. DOJ JUDICIAL VACANCY DASHBOARD
# ============================================================
def scrape_doj_dashboard():
    soup, ok = safe_fetch("https://doj.gov.in/vacancy-positions-2/", "DOJ Vacancy Positions")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "judicial", "presiding", "appointment", "selection", "tribunal", "circular"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://doj.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Dept of Justice", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Central Govt", "type": "doj", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} DOJ Dashboard items")


# ============================================================
# 38. ADDITIONAL HIGH COURTS (EXPANDED)
# ============================================================
def scrape_high_courts_expanded():
    hc_sites = [
        ("https://bombayhighcourt.nic.in/recruitment.php", "Bombay HC"),
        ("https://calcuttahighcourt.gov.in/recruitment", "Calcutta HC"),
        ("https://highcourtofkarnatakaatbangalore.kar.nic.in/recruitment.asp", "Karnataka HC"),
        ("https://highcourtofkerala.nic.in/index.php/vacancy", "Kerala HC"),
        ("https://mphc.gov.in/recruitment-result", "MP HC"),
        ("https://highcourtchd.gov.in/sub_pages/left_menu/recruitment/recruitment.html", "Punjab & Haryana HC"),
        ("https://hcraj.nic.in/hcraj/recruitments.php", "Rajasthan HC"),
        ("https://aphc.gov.in/recruitments.php", "AP HC"),
        ("https://gujarathighcourt.nic.in/recruitment", "Gujarat HC"),
        ("https://orissahighcourt.nic.in/Recruitment.asp", "Orissa HC"),
        ("https://patnahighcourt.gov.in/recruitmentMain.aspx", "Patna HC"),
        ("https://meghalayahighcourt.nic.in/recruitment", "Meghalaya HC"),
        ("https://hptribunalhp.nic.in/", "Himachal Pradesh HC"),
        ("https://thc.nic.in/central/vacancy.aspx", "Tripura HC"),
    ]
    for url, name in hc_sites:
        soup, ok = safe_fetch(url, f"{name} Recruitment")
        if not ok:
            continue
        count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 10:
                keywords = ["judicial", "judge", "district judge", "civil judge", "recruitment",
                            "vacancy", "appointment", "tribunal", "presiding", "member",
                            "judicial service", "law clerk", "registrar"]
                if any(kw in text.lower() for kw in keywords):
                    full_url = href if href.startswith("http") else urljoin(url, href)
                    posted_date, last_date = extract_dates_for_link(link, text)
                    status = compute_status(last_date)
                    add_vacancy({"source": name, "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "High Court", "type": "high_court", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                    count += 1
        log(f"  Found {count} items from {name}")


# ============================================================
# 39. SUPREME COURT OF INDIA
# ============================================================
def scrape_supreme_court():
    soup, ok = safe_fetch("https://www.sci.gov.in/recruitments/", "Supreme Court Recruitments")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "law clerk", "legal", "registrar", "appointment"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://www.sci.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Supreme Court", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Supreme Court", "type": "sci", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} Supreme Court items")


# ============================================================
# 40. CIC - CENTRAL INFORMATION COMMISSION
# ============================================================
def scrape_cic():
    soup, ok = safe_fetch("https://cic.gov.in/", "Central Information Commission")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "commissioner", "appointment", "selection", "circular", "deputation"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://cic.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "CIC", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Information Commission", "type": "cic", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} CIC items")


# ============================================================
# 41. IRDAI - INSURANCE REGULATORY AND DEVELOPMENT AUTHORITY
# ============================================================
def scrape_irdai():
    soup, ok = safe_fetch("https://www.irdai.gov.in/careers", "IRDAI Careers")
    if not ok:
        soup, ok = safe_fetch("https://www.irdai.gov.in/", "IRDAI Homepage")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "appointment", "selection", "deputation", "officer", "legal"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://www.irdai.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "IRDAI", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Insurance Regulator", "type": "irdai", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} IRDAI items")


# ============================================================
# 42. NFRA - NATIONAL FINANCIAL REPORTING AUTHORITY
# ============================================================
def scrape_nfra():
    soup, ok = safe_fetch("https://nfra.gov.in/", "NFRA")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "appointment", "selection", "deputation", "officer", "legal", "circular"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://nfra.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "NFRA", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Financial Reporting Authority", "type": "nfra", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} NFRA items")


# ============================================================
# 43. PFRDA - PENSION FUND REGULATORY AND DEVELOPMENT AUTHORITY
# ============================================================
def scrape_pfrda():
    soup, ok = safe_fetch("https://www.pfrda.org.in/", "PFRDA")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "appointment", "selection", "deputation", "officer", "legal", "circular"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://www.pfrda.org.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "PFRDA", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Pension Fund Regulator", "type": "pfrda", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} PFRDA items")


# ============================================================
# 44. STATE CONSUMER COMMISSIONS - CONFONET
# ============================================================
def scrape_confonet():
    """Scrape confonet.nic.in (National Consumer Disputes directory) for vacancy info."""
    soup, ok = safe_fetch("https://confonet.nic.in/", "Confonet - Consumer Commissions")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "president", "appointment", "selection",
                         "commission", "consumer", "circular", "notification"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://confonet.nic.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Confonet", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "Consumer Commission", "type": "confonet", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} Confonet items")


# ============================================================
# 45. STATE INFORMATION COMMISSIONS
# ============================================================
def scrape_state_info_commissions():
    """Scrape State Information Commissions for vacancy/recruitment notices."""
    sic_sites = [
        ("https://sic.ap.gov.in/", "AP SIC"),
        ("https://sic.telangana.gov.in/", "Telangana SIC"),
        ("https://mahasic.gov.in/", "Maharashtra SIC"),
    ]
    for url, name in sic_sites:
        soup, ok = safe_fetch(url, name)
        if not ok:
            continue
        count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 10:
                keywords = ["vacancy", "recruitment", "commissioner", "appointment", "selection",
                             "deputation", "circular", "notification", "member"]
                if any(kw in text.lower() for kw in keywords):
                    full_url = href if href.startswith("http") else urljoin(url, href)
                    posted_date, last_date = extract_dates_for_link(link, text)
                    status = compute_status(last_date)
                    add_vacancy({"source": name, "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "State Information Commission", "type": "sic", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                    count += 1
        log(f"  Found {count} items from {name}")


# ============================================================
# 46. MAHARASHTRA ADMINISTRATIVE TRIBUNAL (MAT)
# ============================================================
def scrape_maharashtra_at():
    """Scrape Maharashtra Administrative Tribunal (SAT Maharashtra) for vacancies."""
    soup, ok = safe_fetch("https://sat.maharashtra.gov.in/", "Maharashtra Administrative Tribunal", verify=False)
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "judicial", "appointment", "selection",
                         "circular", "notification", "presiding", "registrar"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://sat.maharashtra.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Maharashtra AT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "State Tribunal", "type": "mat", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} Maharashtra AT items")


# ============================================================
# 47. KARNATAKA APPELLATE TRIBUNAL (KAT)
# ============================================================
def scrape_karnataka_at():
    """Scrape Karnataka Appellate Tribunal for vacancies."""
    soup, ok = safe_fetch("https://kapt.karnataka.gov.in/", "Karnataka Appellate Tribunal", verify=False)
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 10:
            keywords = ["vacancy", "recruitment", "member", "judicial", "appointment", "selection",
                         "circular", "notification", "presiding", "registrar"]
            if any(kw in text.lower() for kw in keywords):
                full_url = href if href.startswith("http") else urljoin("https://kapt.karnataka.gov.in/", href)
                posted_date, last_date = extract_dates_for_link(link, text)
                status = compute_status(last_date)
                add_vacancy({"source": "Karnataka AT", "title": text[:200], "url": full_url, "apply_url": None, "detail_url": None, "category": "State Tribunal", "type": "kat", "posted_date": posted_date, "last_date": last_date, "status": status, "scraped_at": datetime.now().isoformat()})
                count += 1
    log(f"  Found {count} Karnataka AT items")


# ============================================================
# NEWS SCRAPERS — tribunal member news from legal platforms
# ============================================================

NEWS_KEYWORDS = re.compile(
    r"tribunal\s*member|judicial\s*member|member\s*appointed|"
    r"presiding\s*officer|chairperson\s*appoint|"
    r"collegium|judicial\s*appointment|"
    r"member\s*\(judicial\)|member\s*\(law\)|"
    r"nclat.*member|nclt.*member|ngt.*member|cat.*member|"
    r"itat.*member|cestat.*member|aft.*member|sat.*member|"
    r"drt.*member|gstat.*member|aptel.*member|tdsat.*member|"
    r"consumer\s*commission.*member|nhrc.*member|"
    r"lokayukta|ombudsman.*appoint|"
    r"tribunal.*reconstitut|tribunal.*appointment|"
    r"vacancy.*tribunal|tribunal.*vacancy|"
    r"high\s*court\s*judge|supreme\s*court\s*judge|"
    r"judicial\s*service\s*exam|district\s*judge.*recruit",
    re.I,
)


def add_news(item):
    """Add a news item."""
    data["news"].append(item)


def scrape_livelaw_news():
    """Scrape LiveLaw for tribunal/judicial appointment news."""
    urls = [
        ("https://www.livelaw.in/tags/tribunal", "LiveLaw - Tribunal"),
        ("https://www.livelaw.in/tags/judicial-appointments", "LiveLaw - Judicial Appointments"),
        ("https://www.livelaw.in/tags/collegium", "LiveLaw - Collegium"),
        ("https://www.livelaw.in/tags/nclt", "LiveLaw - NCLT"),
        ("https://www.livelaw.in/tags/ngt", "LiveLaw - NGT"),
    ]
    for url, label in urls:
        soup, ok = safe_fetch(url, label)
        if not ok:
            continue
        count = 0
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and len(text) > 30 and href and "/news/" in href.lower():
                if NEWS_KEYWORDS.search(text):
                    full_url = href if href.startswith("http") else f"https://www.livelaw.in{href}"
                    posted_date, _ = extract_dates_for_link(link, text)
                    add_news({
                        "source": "LiveLaw",
                        "title": text[:300],
                        "url": full_url,
                        "date": posted_date or datetime.now().strftime("%Y-%m-%d"),
                        "category": label.split(" - ")[-1],
                        "scraped_at": datetime.now().isoformat(),
                    })
                    count += 1
                    if count >= 15:
                        break
        log(f"  Found {count} news from {label}")


def scrape_barandbench_news():
    """Scrape Bar and Bench for tribunal/judicial news."""
    soup, ok = safe_fetch("https://www.barandbench.com/news", "Bar and Bench News")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 30 and href:
            if NEWS_KEYWORDS.search(text):
                full_url = href if href.startswith("http") else f"https://www.barandbench.com{href}"
                posted_date, _ = extract_dates_for_link(link, text)
                add_news({
                    "source": "Bar & Bench",
                    "title": text[:300],
                    "url": full_url,
                    "date": posted_date or datetime.now().strftime("%Y-%m-%d"),
                    "category": "Judicial News",
                    "scraped_at": datetime.now().isoformat(),
                })
                count += 1
                if count >= 15:
                    break
    log(f"  Found {count} news from Bar & Bench")


def scrape_scobserver_news():
    """Scrape SC Observer for Supreme Court / tribunal news."""
    soup, ok = safe_fetch("https://www.scobserver.in/", "SC Observer")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 30 and href:
            if NEWS_KEYWORDS.search(text):
                full_url = href if href.startswith("http") else f"https://www.scobserver.in{href}"
                posted_date, _ = extract_dates_for_link(link, text)
                add_news({
                    "source": "SC Observer",
                    "title": text[:300],
                    "url": full_url,
                    "date": posted_date or datetime.now().strftime("%Y-%m-%d"),
                    "category": "Supreme Court",
                    "scraped_at": datetime.now().isoformat(),
                })
                count += 1
                if count >= 10:
                    break
    log(f"  Found {count} news from SC Observer")


def scrape_verdictum_news():
    """Scrape Verdictum for judicial appointment news."""
    soup, ok = safe_fetch("https://www.verdictum.in/court-updates", "Verdictum Court Updates")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 30 and href:
            if NEWS_KEYWORDS.search(text):
                full_url = href if href.startswith("http") else f"https://www.verdictum.in{href}"
                posted_date, _ = extract_dates_for_link(link, text)
                add_news({
                    "source": "Verdictum",
                    "title": text[:300],
                    "url": full_url,
                    "date": posted_date or datetime.now().strftime("%Y-%m-%d"),
                    "category": "Court Updates",
                    "scraped_at": datetime.now().isoformat(),
                })
                count += 1
                if count >= 10:
                    break
    log(f"  Found {count} news from Verdictum")


def scrape_doj_news():
    """Scrape DOJ press releases for tribunal appointment news."""
    soup, ok = safe_fetch("https://doj.gov.in/", "DOJ Homepage News")
    if not ok:
        return
    count = 0
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if text and len(text) > 20 and href:
            if NEWS_KEYWORDS.search(text):
                full_url = href if href.startswith("http") else urljoin("https://doj.gov.in/", href)
                posted_date, _ = extract_dates_for_link(link, text)
                add_news({
                    "source": "Dept of Justice",
                    "title": text[:300],
                    "url": full_url,
                    "date": posted_date or datetime.now().strftime("%Y-%m-%d"),
                    "category": "Government",
                    "scraped_at": datetime.now().isoformat(),
                })
                count += 1
                if count >= 10:
                    break
    log(f"  Found {count} news from DOJ")


def deduplicate_news():
    """Remove duplicate news items."""
    seen = set()
    unique = []
    for n in data["news"]:
        key = n["title"].lower().strip()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(n)
    data["news"] = sorted(unique, key=lambda x: x.get("date", ""), reverse=True)
    log(f"News after dedup: {len(unique)} items")


# ============================================================
# DEDUPLICATE
# ============================================================
def deduplicate():
    seen = set()
    unique = []
    for v in data["vacancies"]:
        key = (v["title"].lower().strip(), v.get("source", ""))
        if key not in seen:
            seen.add(key)
            unique.append(v)
    data["vacancies"] = unique
    log(f"After dedup: {len(unique)} unique vacancies")


# ============================================================
# FILTER: ONLY JUDICIAL / TRIBUNAL / COMMISSION POSTS
# ============================================================

# Private companies to ALWAYS exclude
EXCLUDE_COMPANIES = [
    "deloitte", "kpmg", "ernst & young", "pwc", "pricewaterhouse",
    "mckinsey", "bain & company", "boston consulting",
    "tata consultancy", "tata communications", "tcs limited",
    "infosys", "wipro", "cognizant", "accenture", "capgemini",
    "amazon", "google", "microsoft", "meta", "apple", "flipkart",
    "reliance industries", "adani", "vedanta",
    "cyril amarchand", "azb & partners", "khaitan", "shardul amarchand",
    "trilegal", "luthra", "nishith desai", "lakshmikumaran", "j sagar",
    "india llp", "pvt ltd", "private limited",
]

# Non-judicial government jobs to exclude (these are govt but NOT relevant for a senior advocate)
EXCLUDE_ROLES = [
    "apprentice", "teacher recruitment", "jbt teacher", "mining sirdar",
    "overman", "laboratory technician", "trainee engineer", "excise inspector",
    "deputy manager recruitment", "staff nurse", "pharmacist", "clerk",
    "stenographer", "data entry", "peon", "driver", "sweeper", "watchman",
    "constable", "sub inspector", "head constable", "asi ", "lineman",
    "electrician", "fitter", "welder", "mechanic", "technician",
    "junior engineer", "assistant engineer", "accounts officer",
]

# Keywords that ALWAYS indicate a relevant judicial/legal vacancy
JUDICIAL_KEYWORDS = [
    "judicial member", "member judicial", "member (judicial", "member (law",
    "presiding officer", "tribunal", "commission", "commissioner",
    "lokayukta", "ombudsman", "advocate general", "public prosecutor",
    "standing counsel", "government pleader", "legal advisor",
    "registrar", "high court", "district court", "supreme court",
    "consumer forum", "consumer commission", "rera",
    "nclt", "nclat", "ncdrc", "itat", "cestat", "cat ", "ngt ", "sat ",
    "gstat", "drt ", "drat ", "aptel", "tdsat", "aft ",
    "judicial service", "law officer", "legal officer",
]



# Positions requiring HC/SC Judge - father (advocate 20 yrs) is NOT eligible
NOT_ELIGIBLE_PATTERNS = [
    # GSTAT Judicial Member requires HC Judge
    (r"gstat.*judicial\s*member", "GSTAT requires HC Judge"),
    (r"gst\s*appellate.*judicial\s*member", "GSTAT requires HC Judge"),
    (r"judicial\s*member.*gstat", "GSTAT requires HC Judge"),
    (r"judicial\s*member.*gst\s*appellate", "GSTAT requires HC Judge"),
    # Lokpal Judicial Member requires HC Judge
    (r"lokpal.*judicial\s*member", "Lokpal requires HC Judge"),
    # RERA Chairperson requires HC Judge (but RERA Member is ok)
    (r"chairperson.*rera", "RERA Chairperson requires HC Judge"),
    (r"chairperson.*real\s*estate\s*appellate", "RERA Chairperson requires HC Judge"),
    # SHRC Chairperson requires HC CJ (but SHRC Member is ok)
    (r"chairperson.*human\s*rights", "SHRC Chairperson requires HC CJ"),
    # Water Disputes Tribunal requires SC/HC Judge
    (r"water\s*disputes\s*tribunal", "Water Disputes Tribunal requires SC/HC Judge"),
]


def filter_non_judicial():
    """Remove private companies, non-judicial jobs, and ineligible positions."""
    before = len(data["vacancies"])
    kept = []
    removed = []

    for v in data["vacancies"]:
        t = v["title"].lower()

        # ELIGIBILITY CHECK: Remove positions requiring HC/SC Judge
        ineligible = False
        for pattern, reason in NOT_ELIGIBLE_PATTERNS:
            if re.search(pattern, t):
                removed.append(("ineligible", v["title"][:60] + f" [{reason}]"))
                ineligible = True
                break
        if ineligible:
            continue

        # Always keep if it has judicial keywords
        if any(kw in t for kw in JUDICIAL_KEYWORDS):
            kept.append(v)
            continue

        # Always remove private companies
        if any(co in t for co in EXCLUDE_COMPANIES):
            removed.append(("private", v["title"][:60]))
            continue

        # Remove non-judicial government roles
        if any(role in t for role in EXCLUDE_ROLES):
            removed.append(("non-judicial", v["title"][:60]))
            continue

        # Keep everything else (tribunal circulars, HC notices, etc.)
        kept.append(v)

    data["vacancies"] = kept
    log(f"Filtered: removed {len(removed)} non-judicial entries, kept {len(kept)}")
    for reason, title in removed:
        log(f"  [{reason}] {title}")


# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 60)
    log("JUDICIAL & TRIBUNAL VACANCY SCRAPER - INDIA")
    log("=" * 60)
    log("")

    # Central Government Portals
    scrape_legal_affairs()
    scrape_doj()
    scrape_upsc()

    # Central Tribunals
    scrape_nclt()
    scrape_nclat()
    scrape_mca()
    scrape_itat()
    scrape_gstat()
    scrape_cerc()
    scrape_drt()
    scrape_rct()
    scrape_aft()
    scrape_aptel()
    scrape_tdsat()
    scrape_sat()

    # Commissions & Authorities
    scrape_ncdrc()
    scrape_nhrc()
    scrape_lokpal()
    scrape_consumer_affairs()
    scrape_cic()
    scrape_confonet()

    # New Tribunals & Bodies
    scrape_ngt()
    scrape_cat()
    scrape_cestat()
    scrape_cci()
    scrape_ibbi()

    # Regulatory Authorities
    scrape_irdai()
    scrape_nfra()
    scrape_pfrda()

    # Senior Advocate Positions
    scrape_nalsa()
    scrape_law_commission()
    scrape_sebi()
    scrape_cgit()
    scrape_doj_dashboard()
    scrape_supreme_court()

    # Ministry
    scrape_labour()

    # High Courts - Tribunal Vacancies
    scrape_allahabad_hc()
    scrape_high_courts()
    scrape_high_courts_expanded()

    # State-level
    scrape_state_rera()
    scrape_state_ercs()
    scrape_state_info_commissions()
    scrape_maharashtra_at()
    scrape_karnataka_at()

    # Job Aggregators
    scrape_livelaw()
    scrape_livelaw_tags()
    scrape_govtjobguru()
    scrape_verdictum()

    # News scrapers — tribunal member news from legal platforms
    scrape_livelaw_news()
    scrape_barandbench_news()
    scrape_scobserver_news()
    scrape_verdictum_news()
    scrape_doj_news()

    deduplicate()
    deduplicate_news()
    filter_non_judicial()

    # Sort vacancies by relevance
    data["vacancies"] = sort_vacancies(data["vacancies"])

    # Generate summary
    summary = generate_summary(data["vacancies"])
    data["summary"] = summary

    # Log summary
    log("")
    log(f"Active vacancies: {summary['active_count']}")
    log(f"Expired vacancies: {summary['expired_count']}")
    log(f"Upcoming deadlines (next 30 days): {len(summary['upcoming_deadlines'])}")
    for item in summary["upcoming_deadlines"]:
        log(f"  - [{item['days_remaining']}d] {item['title'][:80]} ({item['source']})")

    # Save
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Deep scrape stats
    deep_scraped = sum(1 for v in data["vacancies"] if v.get("detail_url"))
    with_pdfs = sum(1 for v in data["vacancies"] if v.get("apply_url"))
    with_last_date = sum(1 for v in data["vacancies"] if v.get("last_date"))
    log(f"Deep-scraped entries: {deep_scraped}")
    log(f"Entries with PDF/apply URL: {with_pdfs}")
    log(f"Entries with last date: {with_last_date}")

    log("")
    log("=" * 60)
    log(f"DONE! Total vacancies found: {len(data['vacancies'])}")
    log(f"Sources checked: {len(data['sources'])}")
    log(f"Errors: {len(data['errors'])}")
    log(f"Data saved to: {output_path}")
    log("=" * 60)

    # ===== AUDIT LOG =====
    audit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.json")
    end_time = datetime.now()
    duration = (end_time - datetime.strptime(data["last_updated"], "%Y-%m-%d %H:%M:%S")).total_seconds()

    sources_ok = [s for s in data["sources"] if s["status"] == "ok"]
    sources_err = [s for s in data["sources"] if s["status"] == "error"]
    active = [v for v in data["vacancies"] if v.get("status") == "active"]
    with_apply = [v for v in data["vacancies"] if v.get("apply_url")]
    with_dates = [v for v in data["vacancies"] if v.get("last_date")]
    new_today = [v for v in active if v.get("posted_date") == end_time.strftime("%Y-%m-%d")]

    audit_entry = {
        "timestamp": end_time.isoformat(),
        "duration_seconds": round(duration),
        "total_vacancies": len(data["vacancies"]),
        "active_vacancies": len(active),
        "expired_vacancies": len(data["vacancies"]) - len(active),
        "with_apply_url": len(with_apply),
        "with_deadline": len(with_dates),
        "new_today": len(new_today),
        "sources_total": len(data["sources"]),
        "sources_ok": len(sources_ok),
        "sources_failed": len(sources_err),
        "failed_sources": [s["name"] for s in sources_err],
        "upcoming_deadlines": len(data.get("summary", {}).get("upcoming_deadlines", [])),
        "errors": data["errors"][:10],
    }

    # Load existing audit log, append, keep last 90 entries
    try:
        with open(audit_path, "r") as f:
            audit_log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        audit_log = []

    audit_log.append(audit_entry)
    audit_log = audit_log[-90:]  # Keep last 90 runs (~45 days)

    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_log, f, ensure_ascii=False, indent=2)

    log(f"Audit log updated: {audit_path}")


if __name__ == "__main__":
    main()
