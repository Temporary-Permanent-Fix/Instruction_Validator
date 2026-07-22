# Packaging Instruction Enrichment & Decision Maker Demo

This app helps the team turn the manual packaging-instruction review process into a repeatable Excel-driven workflow.

## What it does

- Loads the uploaded `Chybné instrukce` workbook.
- Loads the uploaded `Produkty a vlastnosti` workbook.
- Builds cleaned report and product tables.
- Creates case-level enrichment and decision-maker outputs.
- Exports a single readable Excel workbook for internal review and downstream use.

## Required input files

- `Chybné instrukce` Excel file
- `Produkty a vlastnosti` Excel file

Optional:

- `Baliace pravidlá` Excel file

## How to run

1. Open `start_enrichment_maker.bat`
2. Wait for Streamlit to start
3. Upload the two required Excel files
4. Review the results and download the processed workbook

## Exported sheets

The workbook exports these sheets in order:

1. `summary`
2. `decision_summary`
3. `ai_cases_input`
4. `cases_enriched`
5. `cases_mvp`
6. `invalid_reports`
7. `reports_clean`
8. `products_clean`

## What `ai_cases_input` is for

`ai_cases_input` is the filtered, ranked case table prepared for AI Studio or other manual-review workflows.

It keeps the case-level data plus the decision columns, so reviewers can focus on the highest-priority cases without rebuilding the logic manually.
