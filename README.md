# Packaging Instruction Enrichment & Decision Maker

Streamlit app for reviewing and enriching packaging-instruction cases from Excel files.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Or on Windows:

```bat
start_enrichment_maker.bat
```

## Inputs

- `Chybné instrukce` Excel file
- `Produkty a vlastnosti` Excel file

Optional:

- `Baliace pravidlá` Excel file

## Output

The app builds cleaned report/product tables, case enrichment, decision-maker outputs, and exports a single workbook for review.

