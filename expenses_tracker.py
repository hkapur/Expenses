import streamlit as st
import pandas as pd
import io
import time

# --- Configuration ---
st.set_page_config(page_title="H & M Expenses", page_icon="💰", layout="wide")

CATEGORIES = [
    "Rent", "Wifi", "Mobile phone plan", "Hydro/Electricity", "Insurance",
    "Groceries", "Eating Out", "Coffee", "Alcohol", "Travel",
    "Laundry", "Shopping", "Miscellaneous", "Vacation / Entertainment"
]

# --- Session State Management ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = []


# --- Helper Functions ---
def add_expense(category, amount, payer, consumer):
    """Adds a new expense to the session state."""
    st.session_state.expenses.append({
        "Category": category,
        "Amount": float(amount),
        "Payer": payer,
        "Consumer": consumer
    })


def calculate_settlement(data):
    """Calculates totals and who owes whom based on the provided list of dicts."""
    total_paid_h = 0.0
    total_paid_m = 0.0
    cost_h = 0.0
    cost_m = 0.0

    for exp in data:
        amt = float(exp['Amount'])

        # Who Paid (Cash Flow)
        if exp['Payer'] == 'H':
            total_paid_h += amt
        else:
            total_paid_m += amt

        # Who Used (Consumption)
        if exp['Consumer'] == 'Split':
            cost_h += amt / 2
            cost_m += amt / 2
        elif exp['Consumer'] == 'H only':
            cost_h += amt
        else:  # M only
            cost_m += amt

    balance_h = total_paid_h - cost_h
    return total_paid_h, total_paid_m, cost_h, cost_m, balance_h


def generate_csv(data):
    """Generates the CSV string with Google Sheets formulas."""
    grouped = {cat: {"H": [], "M": [], "Split": []} for cat in CATEGORIES}

    for exp in data:
        cat = exp['Category']
        amt = exp['Amount']
        cons = exp['Consumer']

        # Safety check if category was typed manually and not in list
        if cat not in grouped:
            grouped[cat] = {"H": [], "M": [], "Split": []}

        if cons == 'H only':
            grouped[cat]["H"].append(amt)
        elif cons == 'M only':
            grouped[cat]["M"].append(amt)
        else:
            grouped[cat]["Split"].append(amt)

    output = io.StringIO()
    output.write("Category,H Cost (Formula),M Cost (Formula),Total Category Cost\n")

    for cat in grouped:
        h_vals = grouped[cat]["H"]
        m_vals = grouped[cat]["M"]
        s_vals = grouped[cat]["Split"]

        if h_vals or m_vals or s_vals:
            p_h = "+".join(map(str, h_vals)) if h_vals else "0"
            p_m = "+".join(map(str, m_vals)) if m_vals else "0"
            s_all = "+".join(map(str, s_vals)) if s_vals else "0"

            h_formula = f"=(({p_h}) + ({s_all})/2)"
            m_formula = f"=(({p_m}) + ({s_all})/2)"
            total_val = sum(h_vals) + sum(m_vals) + sum(s_vals)

            output.write(f"{cat},{h_formula},{m_formula},{total_val}\n")

    # Summary Section
    tp_h, tp_m, c_h, c_m, bal = calculate_settlement(data)
    settlement_txt = f"M owes H: ${abs(bal):.2f}" if bal > 0 else f"H owes M: ${abs(bal):.2f}"
    if abs(bal) < 0.01: settlement_txt = "All Square"

    output.write("\nSUMMARY,,,\n")
    output.write(f"Total Paid By H,${tp_h:.2f},Total Paid By M,${tp_m:.2f}\n")
    output.write(f"Who Owes Whom?,{settlement_txt},,\n")

    return output.getvalue()


# --- UI Layout ---
st.title("H & M Expense Tracker 💸")

# Top Section: Input Form
with st.expander("Add New Expense", expanded=True):
    with st.form("expense_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            cat_input = st.selectbox("Category", CATEGORIES)
        with c2:
            amt_input = st.number_input("Amount ($)", min_value=0.01, step=0.01, format="%.2f")
        with c3:
            payer_input = st.selectbox("Who Paid?", ["H", "M"])
        with c4:
            consumer_input = st.selectbox("Who Used It?", ["Split", "H only", "M only"])

        submitted = st.form_submit_button("Add Expense", type="primary")

        if submitted:
            add_expense(cat_input, amt_input, payer_input, consumer_input)
            st.success("Expense added! Scroll down to edit or delete.")

st.divider()

# Main Interface: Two Columns
col_left, col_right = st.columns([2, 1], gap="large")

with col_left:
    st.subheader("Expense History (Edit Mode)")
    st.caption("Double-click any cell to edit. Select rows and press 'Delete' to remove.")

    # Convert session state list to DataFrame for the editor
    df = pd.DataFrame(st.session_state.expenses)

    # If df is empty, we need valid columns for the editor to show correctly
    if df.empty:
        df = pd.DataFrame(columns=["Category", "Amount", "Payer", "Consumer"])

    # --- THE DATA EDITOR ---
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",  # Allows Adding/Deleting rows directly in table
        use_container_width=True,
        hide_index=True,
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category",
                help="Select expense category",
                width="medium",
                options=CATEGORIES,
                required=True,
            ),
            "Amount": st.column_config.NumberColumn(
                "Amount ($)",
                help="Cost in USD",
                min_value=0.01,
                format="$%.2f",
                required=True,
            ),
            "Payer": st.column_config.SelectboxColumn(
                "Who Paid?",
                options=["H", "M"],
                required=True,
            ),
            "Consumer": st.column_config.SelectboxColumn(
                "Who Used?",
                options=["Split", "H only", "M only"],
                required=True,
            )
        },
        key="editor"
    )

    # Sync changes back to session state so they persist
    # We convert the edited dataframe back to a list of dicts
    current_data = edited_df.to_dict('records')
    st.session_state.expenses = current_data

with col_right:
    # Use the current_data (from the editor) for calculations immediately
    tp_h, tp_m, cost_h, cost_m, balance = calculate_settlement(current_data)

    st.subheader("Settlement")

    # Styled Result Card
    if abs(balance) < 0.01:
        st.info("All Square!")
    elif balance > 0:
        st.success(f"**M owes H: ${abs(balance):.2f}**")
    else:
        st.warning(f"**H owes M: ${abs(balance):.2f}**")

    st.metric("Total Paid by H", f"${tp_h:.2f}")
    st.metric("Total Paid by M", f"${tp_m:.2f}")

    st.markdown("---")

    # CSV Download
    if current_data:
        csv_data = generate_csv(current_data)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name="monthly_expenses.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True
        )