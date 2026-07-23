# Packaging Instruction Enrichment & Decision Maker Demo

This app turns the manual packaging-instruction review workflow into a clearer Streamlit decision review tool.

## What the app does

- Loads the uploaded `Chybné instrukcie` workbook.
- Loads the uploaded `Produkty a vlastnosti` workbook.
- Builds cleaned report and product tables.
- Produces case-level enrichment and the rule-based decision output.
- Exports the processed workbook for internal use.

## Required input files

- `Chybné instrukcie` Excel file
- `Produkty a vlastnosti` Excel file

Optional:

- `Baliace pravidlá` Excel file

## How to run

1. Double-click `Start_enrichment_maker.bat`
2. Wait for Streamlit to open
3. Upload the required Excel files
4. Click `Process files`
5. Review the dashboard and decision cards

## Exported sheets

The processed workbook keeps these sheets:

1. `summary`
2. `decision_summary`
3. `ai_cases_input`
4. `cases_enriched`
5. `cases_mvp`
6. `reports_clean`
7. `products_clean`

## What `ai_cases_input` is used for

`ai_cases_input` is the filtered case table prepared for downstream AI Studio or manual review workflows.

It contains the cases that match the selected filters and is meant to be the compact handoff table for reviewers.

## Review export

If reviewers save edits in the Decision Review tab, the app also offers a `reviewed_cases.xlsx` export with the review outcome fields.
