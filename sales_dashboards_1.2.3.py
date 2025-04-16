import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date, timedelta
import os
import json

# === CONFIG ===
st.set_page_config(page_title="📈 Sales Forecasting Dashboard", layout="wide")

# === FILE PATHS ===
CREDENTIALS_FILE = "F:/user_credentials.xlsx"
INVOICE_FILE = "data/invoices.csv"
SETTINGS_FILE = "settings.json"

# === DEFAULT TARGETS & PROPORTIONS ===
DEFAULT_TARGET = 1.25e7
DEFAULT_QUARTERS = {
    "Q1": 2500000,
    "Q2": 3000000,
    "Q3": 3500000,
    "Q4": 3500000
}
DEFAULT_PROPORTIONS = {
    "Q1": 0.2,
    "Q2": 0.24,
    "Q3": 0.28,
    "Q4": 0.28
}
MONTHS_MAP = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}

# === SESSION STATE SETUP ===
for key, default in {
    "logged_in": False,
    "username": "",
    "role": "",
    "annual_target": DEFAULT_TARGET,
    "quarter_values": DEFAULT_QUARTERS.copy()
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# === SETTINGS LOADING ===
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    else:
        return {"annual_target": DEFAULT_TARGET, "quarter_values": DEFAULT_QUARTERS.copy()}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

settings = load_settings()
st.session_state.annual_target = settings["annual_target"]
st.session_state.quarter_values = settings["quarter_values"]

# === LOAD CREDENTIALS ===
@st.cache_data(ttl=0)
def load_credentials():
    df = pd.read_excel(CREDENTIALS_FILE, engine='openpyxl')
    return df.set_index("username").to_dict("index")

users = load_credentials()

# === LOGIN SECTION ===
with st.sidebar:
    if not st.session_state.logged_in:
        with st.expander("🔐 Login", expanded=False):
            username = st.text_input("Username").strip().lower()
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if username in users and users[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = users[username]["role"]
                    st.success("✅ Login successful!")
                else:
                    st.error("Invalid username or password")
    else:
        st.write(f"👤 Logged in as: `{st.session_state.username}` ({st.session_state.role})")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.rerun()

# === LOAD INVOICE DATA ===
if os.path.exists(INVOICE_FILE):
    df = pd.read_csv(INVOICE_FILE)
    df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
else:
    df = pd.DataFrame(columns=['company', 'amount', 'datetime', 'entered_by'])

df['date'] = df['datetime'].dt.date
df['year'] = df['datetime'].dt.year
df['month'] = df['datetime'].dt.month

def get_fiscal_quarter(month):
    if month in [4, 5, 6]: return 1
    elif month in [7, 8, 9]: return 2
    elif month in [10, 11, 12]: return 3
    else: return 4

df['quarter'] = df['datetime'].dt.month.apply(get_fiscal_quarter)

# === FILTERING ===
st.sidebar.header("📅 Filter by Date")
available_years = sorted(df['year'].dropna().unique()) or [datetime.today().year]
selected_year = st.sidebar.selectbox("Year", available_years)
available_months = sorted(df[df['year'] == selected_year]['month'].dropna().unique())
selected_months = st.sidebar.multiselect("Months", [MONTHS_MAP[m] for m in available_months],
                                         default=[MONTHS_MAP[m] for m in available_months])
selected_month_nums = [k for k, v in MONTHS_MAP.items() if v in selected_months]

df_filtered = df[df['year'] == selected_year]
if selected_month_nums:
    df_filtered = df_filtered[df_filtered['month'].isin(selected_month_nums)]

companies = df_filtered['company'].dropna().unique().tolist()
selected_companies = st.sidebar.multiselect("Company", companies, default=companies)
df_filtered = df_filtered[df_filtered['company'].isin(selected_companies)]

# === DASHBOARD ===
st.title("📈 Sales Forecasting Dashboard")
st.markdown(f"""<div><strong style='color:gray;'>Total Target:</strong> 
<strong style='color:gray;'>₹{st.session_state.annual_target:,.0f}</strong></div>""", unsafe_allow_html=True)

today = date.today()
fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
fy_end = fy_start.replace(year=fy_start.year + 1) - timedelta(days=1)
days_passed = (today - fy_start).days + 1
days_left = (fy_end - today).days
daily_required = (st.session_state.annual_target - df['amount'].sum()) / days_left if days_left > 0 else 0

# === METRICS ===
st.markdown("### ⏳ Fiscal Year Progress")
col1, col2, col3 = st.columns(3)
col1.metric("🗓️ Days Passed", days_passed)
col2.metric("🍒 Days Left", days_left)
col3.metric("💸 Daily Required", f"₹{daily_required:,.0f}")

achieved_total = df['amount'].sum()
remaining_total = max(0, st.session_state.annual_target - achieved_total)

col4, col5, col6 = st.columns(3)
col4.metric("Achieved", f"₹{achieved_total:,.0f}")
col5.metric("Remaining", f"₹{remaining_total:,.0f}")
col6.metric("Target Completion", f"{(achieved_total / st.session_state.annual_target) * 100:.2f}%")

# === PIE & QUARTERLY BREAKDOWN ===
st.markdown("### 📊 Revenue Distribution & 📊 Quarterly Breakdown")
col1, col2 = st.columns(2)

with col1:
    pie_data = pd.DataFrame({
        "Status": ["Achieved", "Remaining"],
        "Amount": [achieved_total, remaining_total]
    })
    pie_data["Percentage"] = pie_data["Amount"] / st.session_state.annual_target * 100
    pie_chart = alt.Chart(pie_data).mark_arc(innerRadius=50).encode(
        theta="Amount:Q", color="Status:N",
        tooltip=["Status", "Amount", alt.Tooltip("Percentage:Q", format=".1f")]
    ).properties(width=300, height=300)
    st.altair_chart(pie_chart, use_container_width=True)

with col2:
    q_achieved = df.groupby("quarter")["amount"].sum().to_dict()
    for i, q in enumerate(["Q1", "Q2", "Q3", "Q4"], start=1):
        achieved = q_achieved.get(i, 0)
        target = st.session_state.quarter_values[q]
        pct_complete = achieved / target if target else 0
        st.markdown(f"**{q} ({['Apr-Jun','Jul-Sep','Oct-Dec','Jan-Mar'][i-1]})**: ₹{achieved:,.0f} / ₹{target:,.0f}")
        st.progress(min(pct_complete, 1.0))

    if st.session_state.logged_in and st.session_state.role == "admin":
        with st.expander("⚙️ Edit Quarterly Targets (₹)", expanded=False):
            q_inputs = {}
            for q in ["Q1", "Q2", "Q3", "Q4"]:
                q_inputs[q] = st.number_input(f"{q} Target (₹)", value=float(st.session_state.quarter_values[q]), step=50000.0, format="%.0f")
            if st.button("💾 Save Quarterly Targets"):
                total = sum(q_inputs.values())
                if total != st.session_state.annual_target:
                    st.warning(f"⚠️ Total ₹{total:,.0f} doesn't match annual target ₹{st.session_state.annual_target:,.0f}")
                else:
                    st.session_state.quarter_values = q_inputs
                    st.success("✅ Targets updated successfully.")
                    st.rerun()

# === REVENUE OVER TIME ===
st.markdown("### 📊 Revenue Over Time & Monthly Breakdown")
col1, col2 = st.columns(2)

with col1:
    line_data = df_filtered.groupby(df_filtered['datetime'].dt.to_period("M")).sum(numeric_only=True).reset_index()
    line_data['MonthYear'] = line_data['datetime'].astype(str)
    line_chart = alt.Chart(line_data).mark_line(point=True).encode(
        x=alt.X("MonthYear:N", title="Month-Year"),
        y=alt.Y("amount:Q", title="Revenue"),
        tooltip=["MonthYear", "amount"]
    ).properties(height=400)
    st.altair_chart(line_chart, use_container_width=True)

with col2:
    bar_data = df_filtered.groupby("month", as_index=False)['amount'].sum()
    bar_data['month'] = bar_data['month'].apply(lambda x: MONTHS_MAP.get(x, str(x)))
    bar_chart = alt.Chart(bar_data).mark_bar().encode(
        x=alt.X('month:N', title='Month'),
        y=alt.Y('amount:Q', title='Achieved'),
        color=alt.value("steelblue"),
        tooltip=['month', 'amount']
    )
    st.altair_chart(bar_chart, use_container_width=True)

# === ADD INVOICE ===
if st.session_state.logged_in and st.session_state.role in ["admin", "editor"]:
    st.markdown("### ➕ Add New Invoice")
    with st.form("add_invoice_form"):
        company = st.text_input("Company Name")
        amount = st.number_input("Amount", min_value=0.0, step=1000.0)
        date_input = st.date_input("Date", value=date.today())
        time_input = st.time_input("Time", value=datetime.now().time())
        submitted = st.form_submit_button("Add Invoice")
        if submitted and company and amount > 0:
            new_dt = datetime.combine(date_input, time_input)
            new_row = pd.DataFrame([{
                "company": company,
                "amount": amount,
                "datetime": new_dt,
                "entered_by": st.session_state.username
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(INVOICE_FILE, index=False)
            st.success("✅ Invoice added successfully")
            st.rerun()

# === ADMIN PANEL ===
if st.session_state.logged_in and st.session_state.role == "admin":
    st.markdown("### 🛠️ Admin Panel")
    st.markdown("#### 🎯 Update Annual Target")
    new_target = st.number_input("Set New Annual Target (₹)", value=st.session_state.annual_target, step=1e5, format="%.0f")
    if st.button("💾 Save Target"):
        st.session_state.annual_target = new_target
        new_quarters = {q: round(new_target * pct) for q, pct in DEFAULT_PROPORTIONS.items()}
        st.session_state.quarter_values = new_quarters
        save_settings({
            "annual_target": new_target,
            "quarter_values": new_quarters
        })
        st.success("✅ Target and quarters updated.")
        st.rerun()

    st.markdown("#### ⬇️ Download Invoices")
    invoices_excel = df.copy()
    invoices_excel['datetime'] = invoices_excel['datetime'].astype(str)

    @st.cache_data
    def convert_df_to_excel(df):
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Invoices')
        return output.getvalue()

    excel_bytes = convert_df_to_excel(invoices_excel)
    st.download_button(label="📥 Download All Invoices", data=excel_bytes, file_name="all_invoices.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# === ALL INVOICES TABLE ===
if st.session_state.logged_in:
    st.markdown("### 📄 All Invoices")
    st.dataframe(df.sort_values("datetime", ascending=False).reset_index(drop=True))
