"""
pipeline/collector.py — Web data collection for defence companies.

Sources (all free, no API key required):
  - DuckDuckGo text search
  - Wikipedia API
  - Yahoo Finance (via yfinance)
"""

import logging
import urllib.parse

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


# -------------------------------------------------------
# DUCKDUCKGO
# -------------------------------------------------------

def _ddg_search(query: str, max_results: int = 5) -> str:
    """Run a DuckDuckGo text search and return concatenated snippets."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        texts = []
        for r in results:
            title = r.get("title", "")
            body  = r.get("body", "")
            href  = r.get("href", "")
            texts.append(f"[{title}] ({href})\n{body}")
        return "\n\n".join(texts)
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
        return ""


# -------------------------------------------------------
# WIKIPEDIA
# -------------------------------------------------------

def _wikipedia(company: str) -> str:
    """
    Fetch the Wikipedia summary and intro section for a company.
    Uses the Wikipedia REST API — no key required.
    Tries the company name directly, then appends common suffixes if not found.
    """
    candidates = [
        company,
        f"{company} (company)",
        f"{company} (defence)",
    ]

    for candidate in candidates:
        try:
            slug = urllib.parse.quote(candidate.replace(" ", "_"))
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
            resp = requests.get(url, timeout=10, headers={"User-Agent": "DefenceIntelBot/1.0"})
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            if data.get("type") == "disambiguation":
                continue

            # Also fetch the intro section for more detail
            extract = data.get("extract", "")
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            logger.info(f"Wikipedia found: '{candidate}' → {page_url}")
            return f"[Wikipedia: {candidate}] ({page_url})\n{extract}"

        except Exception as e:
            logger.warning(f"Wikipedia fetch failed for '{candidate}': {e}")
            continue

    logger.warning(f"No Wikipedia article found for '{company}'")
    return ""


# -------------------------------------------------------
# PAGE SCRAPING
# -------------------------------------------------------

def _fetch_page_text(url: str, max_chars: int = 15_000) -> str:
    """Fetch a web page and return cleaned text."""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines)[:max_chars]
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return ""


# -------------------------------------------------------
# YAHOO FINANCE
# -------------------------------------------------------

def _resolve_ticker(company: str) -> str:
    """
    Resolve a ticker symbol from a company name using yfinance Search.
    Returns the best-match ticker string, or empty string if not found.
    """
    try:
        import yfinance as yf
        search = yf.Search(company, max_results=5)
        quotes = search.quotes
        if not quotes:
            logger.warning(f"No ticker found for '{company}'")
            return ""
        best = quotes[0]
        ticker = best.get("symbol", "")
        name = best.get("longname") or best.get("shortname") or ""
        logger.info(f"Resolved ticker for '{company}': {ticker} ({name})")
        return ticker
    except Exception as e:
        logger.warning(f"Ticker resolution failed for '{company}': {e}")
        return ""


def _yahoo_finance(ticker: str) -> dict:
    """
    Pull financial data from Yahoo Finance for a given ticker.
    Returns dict with financials by FY and company metadata.
    """
    if not ticker:
        return {}

    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        financials = {}

        inc = stock.financials
        if inc is not None and not inc.empty:
            for col in inc.columns:
                fy  = f"FY{col.year % 100:02d}"
                rev  = inc.at["Total Revenue", col] if "Total Revenue" in inc.index else None
                ebit = inc.at["EBIT", col]          if "EBIT"          in inc.index else None
                net  = inc.at["Net Income", col]    if "Net Income"    in inc.index else None

                entry = {}
                if rev is not None and rev == rev:
                    entry["revenues"] = round(rev / 1e6, 1)
                if ebit is not None and ebit == ebit:
                    entry["ebit"] = round(ebit / 1e6, 1)
                    if rev and rev > 0:
                        entry["ebit_margin"] = round(ebit / rev * 100, 1)
                if net is not None and net == net:
                    entry["net_profit"] = round(net / 1e6, 1)
                    if rev and rev > 0:
                        entry["net_profit_margin"] = round(net / rev * 100, 1)

                if entry:
                    financials[fy] = entry

        info = stock.info or {}
        meta = {
            "employees": info.get("fullTimeEmployees"),
            "sector":    info.get("sector"),
            "industry":  info.get("industry"),
            "website":   info.get("website"),
            "city":      info.get("city"),
            "country":   info.get("country"),
        }

        return {"financials": financials, "info": meta, "ticker_used": ticker}

    except Exception as e:
        logger.warning(f"Yahoo Finance failed for '{ticker}': {e}")
        return {}


# -------------------------------------------------------
# MAIN COLLECTOR
# -------------------------------------------------------

def collect(
    company: str,
    country: str,
    ticker: str = "",
) -> dict:
    """
    Collect raw data about a defence company from multiple sources.
    No API key required.

    Args:
        company:  Company name (e.g. "Thales")
        country:  Country (e.g. "France")
        ticker:   Stock ticker — optional. Auto-resolved from company name if empty.

    Returns a dict with keys:
        - overview:        DuckDuckGo general search results
        - capabilities:    DuckDuckGo defence capabilities results
        - financials_web:  DuckDuckGo financial results
        - relationships:   DuckDuckGo partnerships/customers results
        - wikipedia:       Wikipedia intro section
        - yahoo:           Yahoo Finance structured data
    """
    # DuckDuckGo searches
    queries = {
        "overview":       f"{company} {country} defence company overview",
        "capabilities":   f"{company} defence capabilities products systems",
        "financials_web": f"{company} revenue employees annual report {country}",
        "relationships":  f"{company} defence partnerships customers contracts",
    }

    raw_data = {}
    for key, query in queries.items():
        logger.info(f"Searching: {query}")
        raw_data[key] = _ddg_search(query)

    # Wikipedia
    logger.info(f"Fetching Wikipedia: '{company}'")
    raw_data["wikipedia"] = _wikipedia(company)

    # Yahoo Finance — use provided ticker or resolve from name
    resolved_ticker = ticker.strip()
    if not resolved_ticker:
        logger.info(f"No ticker provided — resolving from company name: '{company}'")
        resolved_ticker = _resolve_ticker(company)

    if resolved_ticker:
        logger.info(f"Fetching Yahoo Finance: {resolved_ticker}")
        raw_data["yahoo"] = _yahoo_finance(resolved_ticker)
    else:
        logger.warning(f"Could not resolve ticker for '{company}' — skipping Yahoo Finance")
        raw_data["yahoo"] = {}

    return raw_data
