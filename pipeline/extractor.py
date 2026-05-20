"""
pipeline/extractor.py — LLM-based structured extraction.

Takes raw web data and uses OpenAI GPT-4o to produce a structured dict
matching the DataBase.xlsm schema used by the Company Profile Generator.
"""

import json
import logging
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# ── Extraction prompt aligned with DataBase.xlsm columns ──
EXTRACTION_PROMPT = """You are a defence industry intelligence analyst.

Given raw web research about a company, extract ALL available information
and return a JSON object with EXACTLY this structure:

{
    "company_name": "Official company name",
    "country": "Country of HQ",
    "field": "Activity domains separated by ' / ' (e.g. 'Missiles / Radar / Electronics')",
    "activity": "1-2 sentence summary of what the company does",
    "locations": "HQ city and key locations (e.g. 'Paris, France; London, UK')",
    "founded": "Year (e.g. '1998')",
    "employees": "Number or range (e.g. '12,000' or '5,000-10,000')",
    "key_people": "CEO and key executives (e.g. 'John Smith (CEO), Jane Doe (CTO)')",
    "type_ownership": "Public / Private / State-owned / Joint Venture / Subsidiary",
    "confidence_index": "1-5 integer rating of data completeness (5=very complete, 1=sparse)",
    "business_overview": "3-5 bullet points on business model, market position, strategy",
    "business_relationships": "Key defence customers, partnerships, joint ventures, associations",
    "capability": "Core industrial capabilities, R&D, production, certifications",
    "notes": "Additional context, analyst observations, data sources used",

    "synthetic_comment": "One-sentence strategic positioning summary for the slide header",

    "financials": {
        "FY22": {"revenues": null, "ebit": null, "ebit_margin": null, "net_profit": null, "net_profit_margin": null},
        "FY23": {"revenues": null, "ebit": null, "ebit_margin": null, "net_profit": null, "net_profit_margin": null},
        "FY24": {"revenues": null, "ebit": null, "ebit_margin": null, "net_profit": null, "net_profit_margin": null},
        "FY25": {"revenues": null, "ebit": null, "ebit_margin": null, "net_profit": null, "net_profit_margin": null}
    },

    "key_facts": {
        "field": "Same as top-level field",
        "locations": "Same as top-level locations",
        "founded": "Same as top-level founded",
        "employees": "Same as top-level employees",
        "key_people": "Same as top-level key_people",
        "type_ownership": "Same as top-level type_ownership"
    }
}

RULES:
- Revenues, EBIT, Net Profit are in EUR millions. Convert from other currencies if needed.
- Margins are percentages (e.g. 12.5 means 12.5%).
- Use null (not "N/A") for unavailable numeric data.
- For text fields, use "N/A" if truly unavailable.
- Be factual — never fabricate financial data.
- Prefer the most recent data available.
- confidence_index: 5 = all fields filled with sourced data, 1 = mostly unknown."""


def extract(
    company: str,
    country: str,
    raw_data: dict,
    api_key: str,
    model: str = "gpt-4o",
) -> dict:
    """
    Extract structured company data from raw web research using OpenAI.

    Args:
        company: Company name.
        country: Country of HQ.
        raw_data: Dict from collector.collect().
        api_key: OpenAI API key.
        model: Model name (gpt-4o, gpt-4o-mini, etc.).

    Returns:
        Structured dict matching DataBase.xlsm schema.
    """
    client = OpenAI(api_key=api_key)

    # Build context from raw data
    context_parts = []
    for key, value in raw_data.items():
        if key == "yahoo" and isinstance(value, dict):
            if value:
                context_parts.append(
                    f"=== YAHOO FINANCE DATA ===\n{json.dumps(value, indent=2, default=str)}"
                )
        elif value:
            context_parts.append(f"=== {key.upper()} ===\n{value}")

    context = "\n\n".join(context_parts)

    # Truncate to fit context window
    max_chars = 100_000
    if len(context) > max_chars:
        context = context[:max_chars]
        logger.info(f"Truncated context to {max_chars} chars")

    user_prompt = (
        f"Company: {company}\nCountry: {country}\n\n"
        f"--- RAW RESEARCH DATA ---\n{context}\n--- END ---\n\n"
        f"Extract all available information into the JSON structure specified."
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # Merge Yahoo Finance financials if LLM missed them
        yahoo = raw_data.get("yahoo", {})
        if yahoo.get("financials"):
            llm_fin = data.get("financials", {})
            for fy, vals in yahoo["financials"].items():
                if fy not in llm_fin or not any(v for v in (llm_fin.get(fy) or {}).values()):
                    llm_fin[fy] = vals
            data["financials"] = llm_fin

        logger.info(f"Extraction successful for {company}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error for {company}: {e}")
        raise
    except Exception as e:
        logger.error(f"Extraction failed for {company}: {e}")
        raise
