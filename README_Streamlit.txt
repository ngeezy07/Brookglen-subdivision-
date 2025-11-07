# Pay App Prototype (Streamlit) — PDF to Dashboard

## Files
- `streamlit_pay_app.py`
- `requirements.txt`
- Seed data in `/mnt/data`: `pay_app_header_latest.csv`, `pay_app_header.csv`, `pay_app_items_seed.csv`

## Run
1) Python 3.10+ recommended.
2) `pip install -r requirements.txt`
3) `streamlit run streamlit_pay_app.py`

## Use
- Optionally upload a pay app PDF to auto-parse the header.
- Or upload header/items CSVs.
- Filter items and export filtered CSV or a full Excel report.
