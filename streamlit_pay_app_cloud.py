
import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO

st.set_page_config(page_title="Pay App Prototype", layout="wide")

# ---------- Loaders ----------
@st.cache_data
def load_default_header():
    df = load_csv("pay_app_header_latest.csv")
    if df is None or (hasattr(df, "empty") and df.empty):
        df = load_csv("pay_app_header.csv")
    return df

@st.cache_data
def load_default_items():
    df = load_csv("pay_app_items_seed.csv")
    return df

@st.cache_data
def load_default_items():
    return load_csv("pay_app_items_seed.csv")

# ---------- Parsing helpers ----------
money_pat = r"\$?([\d]{1,3}(?:,[\d]{3})*(?:\.\d{1,2})|[\d]+(?:\.\d{1,2})?)"
def find_money(label_regex, text):
    m = re.search(label_regex + r".{0,50}?" + money_pat, text, re.IGNORECASE)
    return float(m.group(1).replace(",", "")) if m else None

def find_percent(label_regex, text):
    m = re.search(label_regex + r".{0,50}?(\d{1,3}(?:\.\d{1,2})?)\s*%", text, re.IGNORECASE)
    return float(m.group(1)) if m else None

def find_text(label_regex, text, maxlen=80):
    m = re.search(label_regex + r"\s*[:\-]?\s*([^\n\r]{1," + str(maxlen) + r"})", text, re.IGNORECASE)
    return m.group(1).strip() if m else None

def find_date_range(text):
    m = re.search(r"(Work\s*from|Period\s*from)[^\d]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}).{0,20}?(to|through|–|-).{0,20}?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text, re.IGNORECASE)
    return (m.group(2), m.group(4)) if m else (None, None)

def parse_pdf_to_text(file):
    raw = ""
    try:
        import pdfplumber
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                raw += t + "\n\n---PAGE BREAK---\n\n"
    except Exception:
        try:
            from PyPDF2 import PdfReader
            if hasattr(file, "read"):
                reader = PdfReader(file)
            else:
                reader = PdfReader(str(file))
            for page in reader.pages:
                t = page.extract_text() or ""
                raw += t + "\n\n---PAGE BREAK---\n\n"
        except Exception:
            raw = ""
    return raw

def parse_header_from_text(text):
    # Attempt common fields
    pay_app_no = None
    m_no = re.search(r"(Pay App|Pay Application|Application No\.?)\s*[:#\- ]+\s*(\d+)", text, re.IGNORECASE)
    if m_no:
        try:
            pay_app_no = int(m_no.group(2))
        except Exception:
            pass

    work_from, work_to = find_date_range(text)
    header = {
        "pay_app_no": [pay_app_no],
        "project": [find_text(r"(Project|Project Name)", text)],
        "owner": [find_text(r"(Owner)", text)],
        "engineer": [find_text(r"(Engineer|Consultant)", text)],
        "contractor": [find_text(r"(Contractor)", text)],
        "work_from": [work_from],
        "work_to": [work_to],
        "invoice_date": [find_text(r"(Invoice\s*Date|Application\s*Date|Date)", text, maxlen=20)],
        "original_contract_amount": [find_money(r"(Original\s+Contract\s+Amount|Contract\s+Amount|Original\s+Agreement)", text)],
        "submitted_total_earned_to_date": [find_money(r"(Total\s+Earned\s+to\s+Date|Earned\s+to\s+date|Total\s+Completed\s+&\s+Stored\s+to\s+Date)", text)],
        "percent_complete_value": [find_percent(r"(Percent\s*Complete|% Complete|Percent\s+Complete\s+Value)", text)],
        "retainage_rate_percent": [find_percent(r"(Retainage\s*Rate|Retainage\s*\(\%|\% Retainage)", text)],
        "retainage_to_date": [find_money(r"(Retainage\s+to\s+Date|Total\s+Retainage)", text)],
        "reviewed_amount_this_app": [find_money(r"(Reviewed|Work\s+Completed\s+this\s+Period|This\s+Period\s+Earned)", text)],
        "previous_payments": [find_money(r"(Previous\s+Payments|Less\s+Previous\s+Payments|Less\s+Previous)", text)],
        "amount_due_this_application": [find_money(r"(Amount\s+Due\s+This\s+Application|Net\s+Amount\s+Due|Payment\s+Due)", text)],
    }
    df = pd.DataFrame(header)
    return df

def compute_items(df):
    df = df.copy()
    for c in ["unit_price","bid_qty","this_period_qty","to_date_qty"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["this_period_amount"] = (df.get("this_period_qty", 0) * df.get("unit_price", 0)).round(2)
    df["to_date_amount"] = (df.get("to_date_qty", 0) * df.get("unit_price", 0)).round(2)
    def pct(row):
        bid = row.get("bid_qty", 0)
        tqd = row.get("to_date_qty", 0)
        unit = str(row.get("unit","")).strip().upper()
        if unit == "LS" and bid == 0:
            return np.clip(tqd * 100.0, 0, 100)
        return np.clip((tqd / bid) * 100.0 if bid else 0.0, 0, 100)
    df["pct_complete"] = df.apply(pct, axis=1).round(2)
    return df

def money(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return x

def export_excel(dfs: dict):
    import xlsxwriter
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, frame in dfs.items():
            frame.to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            wb = writer.book
            money_fmt = wb.add_format({"num_format": "$#,##0.00"})
            for idx, col in enumerate(frame.columns):
                ws.set_column(idx, idx, 14)
                if any(k in col for k in ["amount","unit_price"]):
                    ws.set_column(idx, idx, 16, money_fmt)
    output.seek(0)
    return output

# ---------- UI ----------
st.title("Pay Application Prototype")

with st.expander("1) Upload latest Pay App PDF to parse header (optional)"):
    pdf_file = st.file_uploader("Upload PDF", type=["pdf"])
    if pdf_file:
        text = parse_pdf_to_text(pdf_file)
        if not text:
            st.warning("Could not extract text. You can still use CSV uploads below.")
        else:
            hdr = parse_header_from_text(text)
            st.dataframe(hdr)
            if st.button("Use parsed header"):
                st.session_state["header_df"] = hdr

col1, col2 = st.columns(2)
with col1:
    header_csv = st.file_uploader("Upload header CSV", type=["csv"], key="hdr_csv")
with col2:
    items_csv = st.file_uploader("Upload line items CSV", type=["csv"], key="it_csv")

# Load header
if "header_df" in st.session_state:
    header_df = st.session_state["header_df"]
elif header_csv:
    header_df = pd.read_csv(header_csv)
else:
    header_df = load_default_header()

# Load items
if items_csv:
    items_df_raw = pd.read_csv(items_csv)
else:
    items_df_raw = load_default_items()

items_df = compute_items(items_df_raw)

# Summary calcs
if header_df.empty:
    st.error("Header data is empty. Upload header CSV or parse from PDF.")
else:
    h = header_df.iloc[0]
    contract = float(h.get("original_contract_amount") or 0)
    earned = float(h.get("submitted_total_earned_to_date") or items_df["to_date_amount"].sum())
    retain_rate = float(h.get("retainage_rate_percent") or 0) / 100.0
    percent_complete = round((earned / contract) * 100.0, 2) if contract else 0.0
    retain_to_date = round(earned * retain_rate, 2)

    st.subheader("Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Contract", money(contract))
    c2.metric("Earned to Date (Submitted)", money(earned))
    c3.metric("% Complete", f"{percent_complete}%")
    c4.metric("Retainage to Date", money(retain_to_date))
    c5.metric("Reviewed Amount (This App)", money(h.get("reviewed_amount_this_app") or 0))

# Filters and table
st.subheader("Line Items")
moh_choice = st.selectbox("Filter", ["All","Installed only","MOH only"], index=0)
mask_moh = items_df.get("notes","").astype(str).str.upper().eq("MOH")
if moh_choice == "Installed only":
    df_show = items_df[~mask_moh]
elif moh_choice == "MOH only":
    df_show = items_df[mask_moh]
else:
    df_show = items_df

search_txt = st.text_input("Search description")
if search_txt:
    df_show = df_show[df_show["description"].str.contains(search_txt, case=False, na=False)]
min_pct = st.slider("Min % complete", 0.0, 100.0, 0.0, 1.0)
df_show = df_show[df_show["pct_complete"] >= min_pct]

fmt = df_show.copy()
for col in ["unit_price","this_period_amount","to_date_amount"]:
    if col in fmt.columns:
        fmt[col] = fmt[col].map(money)
st.dataframe(fmt, use_container_width=True)

# Exports
st.subheader("Exports")
csv_bytes = df_show.to_csv(index=False).encode("utf-8")
st.download_button("Download filtered items (CSV)", data=csv_bytes, file_name="pay_app_items_filtered.csv", mime="text/csv")

if not header_df.empty:
    report = {
        "Header": header_df,
        "Items (all)": items_df,
        "Items (filtered)": df_show,
    }
    excel_bytes = export_excel(report)
    st.download_button("Download full report (Excel)", data=excel_bytes, file_name="pay_app_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.caption("MOH lines are treated as material-on-hand. Adjust CSVs or parse a new PDF to refresh header values.")
