"""
pipeline/collector.py — Web data collection for defence companies.

Sources:
  - DuckDuckGo text search (no API key needed)
  - Yahoo Finance (for publicly traded companies)
  - Direct website scraping (company site, Wikipedia)
"""

import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


def _ddg_search(query: str, max_results: int = 5) -> str:
    """Run a DuckDuckGo text search and return concatenated snippets."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        texts = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            texts.append(f"[{title}] ({href})\n{body}")
        return "\n\n".join(texts)
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
        return ""


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


def _yahoo_finance(ticker: str) -> dict:
    """
    Pull financial data from Yahoo Finance.
    Returns dict with revenue, ebit, net_income, margins by year.
    """
    if not ticker:
        return {}

    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)

        financials = {}

        # Annual financials
        inc = stock.financials  # columns = dates, rows = line items
        if inc is not None and not inc.empty:
            for col in inc.columns:
                fy = f"FY{col.year % 100}"
                rev = inc.at["Total Revenue", col] if "Total Revenue" in inc.index else None
                ebit = inc.at["EBIT", col] if "EBIT" in inc.index else None
                net = inc.at["Net Income", col] if "Net Income" in inc.index else None

                entry = {}
                if rev and rev == rev:  # not NaN
                    rev_m = round(rev / 1e6, 1)
                    entry["revenues"] = rev_m
                if ebit and ebit == ebit:
                    ebit_m = round(ebit / 1e6, 1)
                    entry["ebit"] = ebit_m
                    if rev and rev > 0:
                        entry["ebit_margin"] = round(ebit / rev * 100, 1)
                if net and net == net:
                    net_m = round(net / 1e6, 1)
                    entry["net_profit"] = net_m
                    if rev and rev > 0:
                        entry["net_profit_margin"] = round(net / rev * 100, 1)

                if entry:
                    financials[fy] = entry

        # Basic info
        info = stock.info or {}
        meta = {
            "employees": info.get("fullTimeEmployees"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "website": info.get("website"),
            "city": info.get("city"),
            "country": info.get("country"),
        }

        return {"financials": financials, "info": meta}

    except Exception as e:
        logger.warning(f"Yahoo Finance failed for {ticker}: {e}")
        return {}


def collect(company: str, country: str, ticker: str = "") -> dict:
    """
    Collect raw data about a defence company from multiple sources.

    Returns a dict with keys:
      - overview: general company search results
      - capabilities: defence capabilities search results
      - financials_web: financial search results
      - relationships: partnerships/customers search results
      - yahoo: Yahoo Finance structured data (if ticker provided)
    """
    queries = {
        "overview": f"{company} {country} defence company overview",
        "capabilities": f"{company} defence capabilities products systems",
        "financials_web": f"{company} revenue employees annual report {country}",
        "relationships": f"{company} defence partnerships customers contracts",
    }

    raw_data = {}
    for key, query in queries.items():
        logger.info(f"Searching: {query}")
        raw_data[key] = _ddg_search(query)

    # Yahoo Finance
    if ticker:
        logger.info(f"Fetching Yahoo Finance: {ticker}")
        raw_data["yahoo"] = _yahoo_finance(ticker)
    else:
        raw_data["yahoo"] = {}

    return raw_data
