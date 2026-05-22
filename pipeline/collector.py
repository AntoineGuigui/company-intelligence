"""
pipeline/collector.py — Web data collection for companies.

Sources (all free, no API key required):
  - DuckDuckGo text search + full page scraping (BeautifulSoup)
  - Wikipedia REST API (structured JSON, no scraping needed)
  - Yahoo Finance via yfinance (structured data, no scraping needed)
"""

import logging
import urllib.parse

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

URLS_TO_SCRAPE = 3  # Number of URLs to scrape per DuckDuckGo query


# -------------------------------------------------------
# DUCKDUCKGO + PAGE SCRAPING
# -------------------------------------------------------

def _fetch_page_text(url: str, max_chars: int = 30_000) -> str:
    """
    Fetch a web page and return cleaned text via BeautifulSoup.
    Returns empty string silently on any error (timeout, block, 403...).
    """
    try:
        resp = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CompanyIntelBot/1.0)"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines)[:max_chars]
    except Exception as e:
        logger.debug(f"Skipped {url}: {e}")
        return ""


def _ddg_search_and_scrape(query: str, max_results: int = 5) -> str:
    """
    Run a DuckDuckGo search, then scrape the top URLS_TO_SCRAPE pages.
    Returns a concatenated string of:
      - DDG snippets for all results
      - Full page text for the top scraped URLs
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
        return ""

    if not results:
        return ""

    parts = []

    # DDG snippets for all results
    for r in results:
        title = r.get("title", "")
        body  = r.get("body", "")
        href  = r.get("href", "")
        parts.append(f"[{title}] ({href})\n{body}")

    # Full page scraping for top N URLs
    scraped = 0
    for r in results:
        if scraped >= URLS_TO_SCRAPE:
            break
        url = r.get("href", "")
        if not url:
            continue
        page_text = _fetch_page_text(url)
        if page_text:
            parts.append(f"=== Full page: {url} ===\n{page_text}")
            scraped += 1
        # If scraping fails, skip silently and try next URL

    return "\n\n".join(parts)


# -------------------------------------------------------
# WIKIPEDIA
# -------------------------------------------------------

def _wikipedia(company: str) -> str:
    """
    Fetch the Wikipedia summary for a company via the REST API (structured JSON).
    No BeautifulSoup needed — Wikipedia returns clean text directly.
    Tries company name, then common suffixes if not found.
    """
    candidates = [
        company,
        f"{company} (company)",
        f"{company} (corporation)",
    ]

    for candidate in candidates:
        try:
            slug = urllib.parse.quote(candidate.replace(" ", "_"))
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
            resp = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "CompanyIntelBot/1.0"},
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            if data.get("type") == "disambiguation":
                continue

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
    Pull structured financial data from Yahoo Finance via yfinance.
    No scraping needed — yfinance returns Python objects directly.
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
                fy   = f"FY{col.year % 100:02d}"
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
    Collect raw data about a company from multiple sources.
    No API key required.

    Pipeline:
      - DuckDuckGo: 4 queries → snippets + full page scraping (top 3 URLs each)
      - Wikipedia:  REST API → structured summary (no scraping)
      - Yahoo Finance: yfinance → structured financials (no scraping)

    Args:
        company: Company name (e.g. "Thales")
        country: Country (e.g. "France")
        ticker:  Stock ticker — optional. Auto-resolved from company name if empty.

    Returns a dict with keys:
        - overview, capabilities, financials_web, relationships: DDG + scraped pages
        - wikipedia: Wikipedia summary
        - yahoo: Yahoo Finance structured data
    """
    queries = {
        "overview":       f"{company} {country} company overview",
        "capabilities":   f"{company} products services capabilities",
        "financials_web": f"{company} revenue employees annual report {country}",
        "relationships":  f"{company} partnerships customers contracts",
    }

    raw_data = {}

    # DuckDuckGo + page scraping
    for key, query in queries.items():
        logger.info(f"Searching + scraping: {query}")
        raw_data[key] = _ddg_search_and_scrape(query)

    # Wikipedia (structured JSON — no scraping)
    logger.info(f"Fetching Wikipedia: '{company}'")
    raw_data["wikipedia"] = _wikipedia(company)

    # Yahoo Finance (structured data — no scraping)
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
