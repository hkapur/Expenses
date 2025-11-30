import streamlit as st
import pandas as pd
import io
import time

# --- Configuration ---
st.set_page_config(page_title="H & M Expenses", page_icon="💰")

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
        "id": time.time(),  # Simple unique ID
        "Category": category,
        "Amount": amount,
        "Payer": payer,
        "Consumer": consumer
    })


def remove_expense(index):
    """Removes an expense by index."""
    st.session_state.expenses.pop(index)


def calculate_settlement():
    """Calculates totals and who owes whom."""
    total_paid_h = 0.0
    total_paid_m = 0.0
    cost_h = 0.0
    cost_m = 0.0

    for exp in st.session_state.expenses:
        amt = exp['Amount']

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

    # Net Balance: Positive means M owes H, Negative means H owes M
    # Logic: (Amount H Paid) - (Amount H Consumed)
    # If H paid 100 but only ate 50, balance is +50 (H is owed 50)
    balance_h = total_paid_h - cost_h

    return total_paid_h, total_paid_m, cost_h, cost_m, balance_h


def generate_csv():
    """Generates the CSV string with Google Sheets formulas."""
    grouped = {cat: {"H": [], "M": [], "Split": []} for cat in CATEGORIES}

    # Organize data
    for exp in st.session_state.expenses:
        cat = exp['Category']
        amt = exp['Amount']
        cons = exp['Consumer']

        if cons == 'H only':
            grouped[cat]["H"].append(amt)
        elif cons == 'M only':
            grouped[cat]["M"].append(amt)
        else:
            grouped[cat]["Split"].append(amt)

    # Build CSV Rows
    output = io.StringIO()
    output.write("Category,H Cost (Formula),M Cost (Formula),Total Category Cost\n")

    for cat in CATEGORIES:
        h_vals = grouped[cat]["H"]
        m_vals = grouped[cat]["M"]
        s_vals = grouped[cat]["Split"]

        # Only write if there's data
        if h_vals or m_vals or s_vals:
            # Create formula string: =((20+10) + (50+30)/2)
            p_h = "+".join(map(str, h_vals)) if h_vals else "0"
            p_m = "+".join(map(str, m_vals)) if m_vals else "0"
            s_all = "+".join(map(str, s_vals)) if s_vals else "0"

            h_formula = f"=(({p_h}) + ({s_all})/2)"
            m_formula = f"=(({p_m}) + ({s_all})/2)"

            total_val = sum(h_vals) + sum(m_vals) + sum(s_vals)

            output.write(f"{cat},{h_formula},{m_formula},{total_val}\n")

    # Summary Section
    tp_h, tp_m, c_h, c_m, bal = calculate_settlement()
    settlement_txt = f"M owes H: ${abs(bal):.2f}" if bal > 0 else f"H owes M: ${abs(bal):.2f}"
    if abs(bal) < 0.01: settlement_txt = "All Square"

    output.write("\nSUMMARY,,,\n")
    output.write(f"Total Paid By H,${tp_h:.2f},Total Paid By M,${tp_m:.2f}\n")
    output.write(f"Who Owes Whom?,{settlement_txt},,\n")

    return output.getvalue()


# --- UI Layout ---

st.title("H & M Expense Tracker 💸")
st.markdown("Add monthly expenses and calculate who owes whom.")

# Create two columns for layout: Input Form (Left) and Summary/List (Right)
col1, col2 = st.columns([1, 1.5], gap="large")

with col1:
    st.subheader("Add New Expense")

    with st.form("expense_form", clear_on_submit=True):
        cat_input = st.selectbox("Category", CATEGORIES)
        amt_input = st.number_input("Amount ($)", min_value=0.01, step=0.01, format="%.2f")

        # Radio buttons for quick selection
        payer_input = st.radio("Who Paid?", ["H", "M"], horizontal=True)
        consumer_input = st.radio("Who Used It?", ["Split", "H only", "M only"], horizontal=True)

        submitted = st.form_submit_button("Add Expense", use_container_width=True, type="primary")

        if submitted:
            add_expense(cat_input, amt_input, payer_input, consumer_input)
            st.success(f"Added ${amt_input} to {cat_input}")

with col2:
    # Calculate Settlement
    tp_h, tp_m, cost_h, cost_m, balance = calculate_settlement()

    st.subheader("Settlement")

    # Styled Result Card
    if abs(balance) < 0.01:
        st.info("You are all square!")
    elif balance > 0:
        st.info(f"👉 **M owes H: ${abs(balance):.2f}**")
    else:
        st.info(f"👉 **H owes M: ${abs(balance):.2f}**")

    # Metrics Row
    m1, m2 = st.columns(2)
    m1.metric("Total Paid by H", f"${tp_h:.2f}")
    m2.metric("Total Paid by M", f"${tp_m:.2f}")

    st.divider()

    # Expense List
    st.subheader("History")

    if st.session_state.expenses:
        # Display custom table with delete buttons
        # Header
        col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([3, 2, 1.5, 2, 1])
        col_h1.markdown("**Category**")
        col_h2.markdown("**Amount**")
        col_h3.markdown("**Paid**")
        col_h4.markdown("**Used**")
        col_h5.markdown("**Del**")

        # Iterate through expenses (newest first)
        for i, exp in enumerate(reversed(st.session_state.expenses)):
            # Calculate original index because we are iterating in reverse
            original_index = len(st.session_state.expenses) - 1 - i

            c1, c2, c3, c4, c5 = st.columns([3, 2, 1.5, 2, 1])
            c1.write(exp["Category"])
            c2.write(f"${exp['Amount']:.2f}")
            c3.write(exp["Payer"])
            c4.write(exp["Consumer"])

            # Delete button with unique key based on expense ID
            if c5.button("🗑️", key=f"del_{exp['id']}", help="Delete this expense"):
                remove_expense(original_index)
                st.rerun()

        # CSV Download
        csv_data = generate_csv()
        st.download_button(
            label="Download CSV for Google Sheets",
            data=csv_data,
            file_name="monthly_expenses.csv",
            mime="text/csv",
            type="secondary"
        )
    else:
        st.caption("No expenses added yet.")