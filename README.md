# EcoBuilder

EcoBuilder compares the embodied carbon of construction products using a shared SQLite retailer catalog. The Client Dashboard has an OpenAI-powered chat. The Retailer Dashboard lets each retailer update its own listings.

## Run locally on Windows

Use Python 3.12 in PowerShell from the project directory.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe backend.py init-db
.\.venv\Scripts\python.exe -m streamlit run frontend.py
```

To enable chat, set `OPENAI_API_KEY` in the PowerShell session before starting Streamlit. On PowerShell 7, `$env:OPENAI_API_KEY = Read-Host "OpenAI API key" -MaskInput` prompts without echoing the key. The app defaults to `gpt-4o-mini`. Set `OPENAI_MODEL` to use another model with Structured Outputs support. The catalog and retailer tools also run without a key. [OpenAI API quickstart](https://developers.openai.com/api/docs/quickstart)

## Try a comparison

From **Client Dashboard**, enter “Compare BuildMix M25.” The demo compares BuildMix M25 at 312 kg CO₂e/m³ with EcoMix M25 at 238 kg CO₂e/m³. EcoMix M25 is 74 kg CO₂e/m³ lower in this illustrative comparison. You can ask for multiple products in one message, such as “Compare BuildMix M25 and BuildBase OPC 43.” Each product gets its own comparison group.

The demo covers cement, ready-mix concrete, rebar, masonry blocks, sand, coarse aggregate, structural timber, and roofing. Names, retailers, and seeded emissions figures are fictional. The comparison uses the A1–A3 product stage and the catalog unit for that specification. When adding a product, use a source with the same scope, unit, and technical specification as the other listings in its group. [EPD International example and comparability criteria](https://environdec.com/library/epd30963)

## Set up retailer accounts

Set a different password for each seeded account using the hidden prompts.

```powershell
.\.venv\Scripts\python.exe backend.py set-password greenfield
.\.venv\Scripts\python.exe backend.py set-password cornerstone
```

Sign in on the **Retailer Dashboard** to add, edit, deactivate, or reactivate your listings. Deactivated listings are hidden from client lookups. Changes are saved in `ecobuilder.sqlite3`. Database initialization runs automatically when the app starts, and rerunning it preserves retailer edits. For a separate test catalog, set `ECOBUILDER_DB` to a different SQLite file path before running the app or commands.

The original `prototype_dataset1.xlsx` is retained for the legacy report.
