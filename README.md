# 🔍 Company Intelligence Generator

Automated competitive intelligence pipeline. Generates structured company profiles from web research (DuckDuckGo + Wikipedia + Yahoo Finance) via GPT-4o extraction, outputting directly into a `DataBase.xlsm`-compatible Excel format.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B?logo=streamlit&logoColor=white)
![OpenAI](https://img.shields.io/badge/GPT--4o-Extraction-412991?logo=openai&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🎯 What it does

For any company, the tool:

1. **Collects** data from the web (DuckDuckGo + Wikipedia) + financial data (Yahoo Finance)
2. **Extracts** structured intelligence via GPT-4o using a company analysis framework
3. **Writes** results into an Excel database matching the `DataBase.xlsm` schema

The output Excel is directly compatible with the [Company Profile Generator](https://github.com/AntoineGuigui/company-intelligence-toolkit) — one tool feeds the other.

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   DuckDuckGo    │────▶│                  │     │                  │
│   Web Search    │     │   GPT-4o         │────▶│  DataBase.xlsx   │
│                 │     │   Structured     │     │  (6 sheets)      │
│   Wikipedia     │────▶│   Extraction     │     │                  │
│                 │     │                  │     │                  │
│   Yahoo Finance │────▶│                  │     │                  │
└─────────────────┘     └──────────────────┘     └──────────────────┘
   collector.py             extractor.py          excel_generator.py
```

```
company-intelligence/
├── app.py                          # Streamlit web interface
├── pipeline/
│   ├── __init__.py
│   ├── collector.py                # DuckDuckGo + Wikipedia + Yahoo Finance
│   ├── extractor.py                # GPT-4o structured extraction
│   └── excel_generator.py          # Write to DataBase.xlsm format
├── outputs/                        # Generated Excel files
├── requirements.txt
└── .env.example
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/AntoineGuigui/company-intelligence.git
cd company-intelligence
pip install -r requirements.txt
streamlit run app.py
```

Then enter your OpenAI API key in the sidebar and start analysing companies.

---

## 📊 Output Format

The generated Excel follows the exact schema expected by the Company Profile Generator:

### DataBase sheet (14 columns)

| Column | Description |
|---|---|
| Company Name | Official name |
| Country | HQ country |
| Field | Activity domains |
| Activity | 1-2 sentence summary |
| Locations | HQ + key sites |
| Founded | Year |
| N° employees | Headcount |
| Key people | CEO, key executives |
| Type Ownership | Public / Private / State-owned / JV |
| Confidence Index | 1-5 data quality rating |
| Business Overview | Strategic summary |
| Business relationships | Partners, customers, alliances |
| Capability | Core capabilities, R&D |
| Notes | Additional context, sources |

### Financial sheets (5 sheets, same structure)

Each sheet has `Company` + year columns (2022, 2023, 2024, 2025):
- **Revenue** — in EUR millions
- **EBIT** — in EUR millions
- **Net Profit** — in EUR millions
- **EBIT Margin** — percentage
- **Net Profit Margin** — percentage

---

## ⚙️ Configuration

In the Streamlit sidebar:
- **OpenAI API Key**: Required (`sk-...`)
- **Model**: `gpt-4o` (best quality) or `gpt-4o-mini` (~10x cheaper)
- **Ticker**: Optional — auto-resolved from company name for public companies

---

## 💡 Example Companies

| Company | Country | Ticker |
|---|---|---|
| Thales | France | HO.PA |
| MBDA | France | *(private)* |
| Rheinmetall | Germany | RHM.DE |
| Apple | USA | AAPL |
| Airbus | France | AIR.PA |
| Siemens | Germany | SIE.DE |

---

## 🔗 Integration with Company Profile Generator

This tool is designed as **Module 1** of a two-part pipeline:

```
[Intelligence Generator]  →  DataBase.xlsx  →  [Profile Generator]  →  PPTX slides
      (this repo)                                  (Flask app)
```

Copy the generated `DataBase.xlsx` to your Company Profile Generator project folder, rename to `DataBase.xlsm` if needed, and the Flask interface will load it automatically.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Interface | Streamlit |
| Web search | DuckDuckGo (no API key) |
| Encyclopedia | Wikipedia REST API (no API key) |
| Financial data | Yahoo Finance (yfinance, no API key) |
| LLM extraction | OpenAI GPT-4o / GPT-4o-mini |
| Excel output | openpyxl |
| HTML parsing | BeautifulSoup, lxml |

---

## ⚠️ Limitations

- Web data is public-only — **verify** critical financial figures
- Financial data from Yahoo Finance is only available for publicly traded companies
- Private or poorly documented companies will have sparse fields
- Expect ~30-60 seconds per company (depends on OpenAI latency)

---

## 📄 License

MIT — see [LICENSE](LICENSE).

## 👤 Author

**Antoine Guigui** — CentraleSupélec '26  
[LinkedIn](https://www.linkedin.com/in/antoine-guigui-846266132/)
