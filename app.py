import json
import math
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

# ---------------------------------------------------------
# Page Configuration & Constants (NUR-3 | AP Calculus)
# ---------------------------------------------------------
st.set_page_config(
    page_title="LIFESAVERS | NUR-3 Health Education Simulation",
    layout="wide"
)

PATHWAY_ID = "NUR-3"
COURSE_NAME = "AP Calculus"
BUSINESS_NAME = "Nurse-led health education simulation"

# Default NUR-3 Parameters (Handbook p. 83)
DEFAULTS = {
    "team_id": "LIFESAVERS",
    "pathway_id": PATHWAY_ID,
    "selected_course": COURSE_NAME,
    "selected_level": "Foundation",
    "state_version": 1,
    "base_price": Decimal("25.00"),
    "D0": 80,
    "staff_hours": 30.0,
    "hours_per_unit": 0.5,
    "venue_seats": 60,
    "no_show_rate": 0.0,
    "satisfaction_mean": 4.0,
    "owner_contribution": Decimal("6000.00"),
    "equipment_assets": Decimal("1500.00"),
    "pre_opening_expense": Decimal("500.00"),
    "opening_cash": Decimal("4000.00"),
    "var_educator": Decimal("2.00"),
    "var_materials": Decimal("2.00"),
    "var_cleaning": Decimal("1.00"),
    "fix_venue": Decimal("250.00"),
    "fix_software": Decimal("100.00"),
    "fix_accessibility": Decimal("200.00"),
    "fix_admin_insurance": Decimal("150.00"),
}

# Exact Monthly Fixture Data (Handbook p. 85)
MONTHLY_FIXTURE = [
    {"month": "2027-01", "requested": 80, "capacity_override": 60, "ad_cost": Decimal("0.00")},
    {"month": "2027-02", "requested": 88, "capacity_override": 60, "ad_cost": Decimal("100.00")},
    {"month": "2027-03", "requested": 72, "capacity_override": 45, "ad_cost": Decimal("0.00")},
]


def money(val) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def init_state():
    if "sim" not in st.session_state:
        st.session_state.sim = {
            "team_id": DEFAULTS["team_id"],
            "pathway_id": PATHWAY_ID,
            "selected_course": COURSE_NAME,
            "selected_level": DEFAULTS["selected_level"],
            "state_version": 1,
            "snapshot_id": "SNAP-001",
            "cash": float(DEFAULTS["opening_cash"]),
            "equipment_assets": float(DEFAULTS["equipment_assets"]),
            "owner_equity": float(DEFAULTS["owner_contribution"]),
            "retained_earnings": float(-DEFAULTS["pre_opening_expense"]),
            "debt": 0.0,
            "params": {
                "base_price": float(DEFAULTS["base_price"]),
                "D0": DEFAULTS["D0"],
                "staff_hours": DEFAULTS["staff_hours"],
                "hours_per_unit": DEFAULTS["hours_per_unit"],
                "venue_seats": DEFAULTS["venue_seats"],
                "no_show_rate": DEFAULTS["no_show_rate"],
                "satisfaction_mean": DEFAULTS["satisfaction_mean"],
                "var_educator": float(DEFAULTS["var_educator"]),
                "var_materials": float(DEFAULTS["var_materials"]),
                "var_cleaning": float(DEFAULTS["var_cleaning"]),
                "fix_venue": float(DEFAULTS["fix_venue"]),
                "fix_software": float(DEFAULTS["fix_software"]),
                "fix_accessibility": float(DEFAULTS["fix_accessibility"]),
                "fix_admin_insurance": float(DEFAULTS["fix_admin_insurance"]),
            },
            "ledger": [],
            "processed_run_ids": [],
        }


init_state()
sim = st.session_state.sim
params = sim["params"]

# ---------------------------------------------------------
# Deterministic Business Calculations (NUR-3 Rules, p. 84)
# ---------------------------------------------------------
def compute_unit_costs(p: dict):
    var_unit = money(p["var_educator"]) + money(p["var_materials"]) + money(p["var_cleaning"])
    fixed_month = (
        money(p["fix_venue"])
        + money(p["fix_software"])
        + money(p["fix_accessibility"])
        + money(p["fix_admin_insurance"])
    )
    return var_unit, fixed_month


def run_monthly_step(
    requested: int,
    p: dict,
    ad_cost: Decimal = Decimal("0.00"),
    capacity_override: int | None = None,
    refund_amount: Decimal = Decimal("0.00"),
    loan_cash: Decimal = Decimal("0.00"),
    principal_repaid: Decimal = Decimal("0.00"),
    interest_paid: Decimal = Decimal("0.00"),
    additional_capex: Decimal = Decimal("0.00"),
):
    staff_cap = math.floor(p["staff_hours"] / p["hours_per_unit"]) if p["hours_per_unit"] > 0 else 0
    derived_capacity = min(staff_cap, int(p["venue_seats"]))
    effective_capacity = capacity_override if capacity_override is not None else derived_capacity

    booked = min(int(requested), effective_capacity)
    attended = math.floor(booked * (1.0 - float(p["no_show_rate"])))
    sold = attended
    unserved_demand = max(0, int(requested) - booked)

    price = money(p["base_price"])
    var_unit, fixed_month = compute_unit_costs(p)

    gross_revenue = price * Decimal(sold)
    net_revenue = gross_revenue - money(refund_amount)
    variable_expense = var_unit * Decimal(sold)
    total_operating_expense = variable_expense + fixed_month + money(ad_cost)
    operating_profit = net_revenue - total_operating_expense
    net_profit = operating_profit - money(interest_paid)

    cash_delta = (
        net_revenue
        - variable_expense
        - fixed_month
        - money(ad_cost)
        - money(interest_paid)
        - money(principal_repaid)
        - money(additional_capex)
        + money(loan_cash)
    )

    return {
        "derived_capacity": derived_capacity,
        "effective_capacity": effective_capacity,
        "requested": int(requested),
        "booked": booked,
        "attended": attended,
        "sold": sold,
        "unserved_demand": unserved_demand,
        "revenue": net_revenue,
        "variable_expense": variable_expense,
        "fixed_expense": fixed_month,
        "ad_cost": money(ad_cost),
        "total_expense": total_operating_expense,
        "operating_profit": operating_profit,
        "net_profit": net_profit,
        "cash_delta": cash_delta,
    }


# ---------------------------------------------------------
# Sidebar: Control Metadata & JSON Snapshot Save/Restore
# ---------------------------------------------------------
st.sidebar.title("System Controls")
st.sidebar.info(
    "**Educational Simulation Only:** Fictional general health education workshops. "
    "No clinical diagnosis, medical treatment, or real patient data."
)

sim["team_id"] = st.sidebar.text_input("Team ID", value=sim["team_id"])
sim["selected_level"] = st.sidebar.selectbox(
    "Teacher-Approved Math Level",
    ["Foundation", "Applied", "Advanced"],
    index=["Foundation", "Applied", "Advanced"].index(sim["selected_level"]),
)
st.sidebar.markdown(f"**Pathway:** `{PATHWAY_ID}` ({COURSE_NAME})")
st.sidebar.markdown(f"**State Version:** `v{sim['state_version']}`")
st.sidebar.markdown(f"**Snapshot ID:** `{sim['snapshot_id']}`")

st.sidebar.divider()
st.sidebar.subheader("Durable Save / Restore (JSON)")

snapshot_payload = json.dumps(sim, indent=2)
st.sidebar.download_button(
    label="Export Snapshot JSON",
    data=snapshot_payload,
    file_name=f"{sim['team_id']}_{PATHWAY_ID}_v{sim['state_version']}.json",
    mime="application/json",
)

uploaded_json = st.sidebar.file_uploader("Import Snapshot JSON", type=["json"])
if uploaded_json is not None:
    if st.sidebar.button("Restore Uploaded Snapshot"):
        try:
            loaded = json.load(uploaded_json)
            required_keys = {"team_id", "pathway_id", "state_version", "cash", "params", "ledger"}
            if not required_keys.issubset(loaded.keys()):
                st.sidebar.error("Rejected: Missing required snapshot fields.")
            elif loaded["team_id"] != sim["team_id"]:
                st.sidebar.error(
                    f"Rejected: Team ID mismatch (expected '{sim['team_id']}', got '{loaded['team_id']}')."
                )
            elif loaded["pathway_id"] != PATHWAY_ID:
                st.sidebar.error(f"Rejected: Pathway mismatch (expected '{PATHWAY_ID}').")
            elif int(loaded["state_version"]) < int(sim["state_version"]):
                st.sidebar.error(
                    f"Rejected: Stale version v{loaded['state_version']} (current is v{sim['state_version']})."
                )
            else:
                st.session_state.sim = loaded
                st.sidebar.success(f"Restored snapshot v{loaded['state_version']}!")
                st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Rejected invalid JSON: {exc}")

if st.sidebar.button("Reset to Opening Baseline"):
    del st.session_state.sim
    st.rerun()

# ---------------------------------------------------------
# Header & Top KPI Summary
# ---------------------------------------------------------
st.title(f"{sim['team_id']} — {BUSINESS_NAME}")
st.caption(
    f"Stage 1 Build | Course: {COURSE_NAME} | Pathway: {PATHWAY_ID} | "
    f"Mode: Manual Workflow (No Paid APIs Required)"
)

var_u, fix_m = compute_unit_costs(params)
derived_cap = min(
    math.floor(params["staff_hours"] / params["hours_per_unit"]) if params["hours_per_unit"] > 0 else 0,
    int(params["venue_seats"]),
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Current Spendable Cash", f"${sim['cash']:,.2f}")
k2.metric("Derived Monthly Capacity", f"{derived_cap} seats")
k3.metric("Variable Cost / Seat", f"${var_u:,.2f}")
k4.metric("Fixed Cost / Month", f"${fix_m:,.2f}")

# ---------------------------------------------------------
# Navigation Tabs (Stage 1 Core Modules)
# ---------------------------------------------------------
tab_inputs, tab_math, tab_sim, tab_tests = st.tabs([
    "1. Inputs & Funding",
    "2. AP Calculus Math Panel",
    "3. Run Simulation & Ledger",
    "4. Stage 1 Acceptance Tests",
])

# =========================================================
# TAB 1: INPUTS & FUNDING
# =========================================================
with tab_inputs:
    st.subheader("Startup Capital & Opening Balance Sheet (Fictional Teaching Defaults)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Owner Contribution", "$6,000.00")
    c2.metric("Equipment Assets", f"${sim['equipment_assets']:,.2f}")
    c3.metric("Pre-Opening Expense", "$500.00")
    c4.metric("Post-Startup Opening Cash", "$4,000.00")

    st.divider()
    st.subheader("Editable Operating Parameters & Cost Lines")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Pricing, Demand & Capacity**")
        params["base_price"] = st.number_input("Base Price per Seat ($)", min_value=1.0, value=float(params["base_price"]), step=1.0)
        params["D0"] = st.number_input("Baseline Monthly Demand D0 (seats)", min_value=0, value=int(params["D0"]), step=1)
        params["staff_hours"] = st.number_input("Educator Staff Hours / Month", min_value=0.0, value=float(params["staff_hours"]), step=1.0)
        params["hours_per_unit"] = st.number_input("Educator Hours per Seat", min_value=0.1, value=float(params["hours_per_unit"]), step=0.1)
        params["venue_seats"] = st.number_input("Venue Seat Limit / Month", min_value=0, value=int(params["venue_seats"]), step=1)
        params["no_show_rate"] = st.slider("No-Show Rate (0.0 to 1.0)", min_value=0.0, max_value=1.0, value=float(params["no_show_rate"]), step=0.05)

    with col_b:
        st.markdown("**Variable Costs ($ / Attended Seat)**")
        params["var_educator"] = st.number_input("Educator Delivery ($/seat)", min_value=0.0, value=float(params["var_educator"]), step=0.5)
        params["var_materials"] = st.number_input("Workshop Materials ($/seat)", min_value=0.0, value=float(params["var_materials"]), step=0.5)
        params["var_cleaning"] = st.number_input("Cleaning Consumables ($/seat)", min_value=0.0, value=float(params["var_cleaning"]), step=0.5)

        st.markdown("**Fixed Monthly Expenses ($ / Month)**")
        params["fix_venue"] = st.number_input("Venue Rent ($/mo)", min_value=0.0, value=float(params["fix_venue"]), step=10.0)
        params["fix_software"] = st.number_input("Scheduling Software ($/mo)", min_value=0.0, value=float(params["fix_software"]), step=10.0)
        params["fix_accessibility"] = st.number_input("Accessibility & Translation Support ($/mo)", min_value=0.0, value=float(params["fix_accessibility"]), step=10.0)
        params["fix_admin_insurance"] = st.number_input("Admin & Insurance Assumption ($/mo)", min_value=0.0, value=float(params["fix_admin_insurance"]), step=10.0)

# =========================================================
# TAB 2: AP CALCULUS MATH PANEL (Adapter p. 70 & NUR-3 p. 37)
# =========================================================
with tab_math:
    level = sim["selected_level"]
    p0 = float(params["base_price"])
    D0 = float(params["D0"])
    v = float(var_u)
    F = float(fix_m)
    cap = float(derived_cap)

    a = 2.0 * D0
    b = D0 / p0 if p0 > 0 else 0.0
    p_max = 2.0 * p0
    p_unconstrained = (a + b * v) / (2.0 * b) if b > 0 else 0.0
    p_cap_corner = (a - cap) / b if b > 0 else 0.0

    st.subheader(f"AP Calculus Math Skills Panel — Level: {level}")

    if level == "Foundation":
        st.markdown(
            f"""
            **Business Question:** What workshop seat price $p$ maximizes unconstrained monthly operating profit?  
            **Demand Model:** $q(p) = {a:.1f} - {b:.2f}p$ on domain $0 \le p \le {p_max:.2f}$ (seats/month)  
            **Profit Function:** $P(p) = (p - {v:.2f})({a:.1f} - {b:.2f}p) - {F:.2f}$ ($/month)  
            **Derivative:** $P'(p) = {a + b*v:.2f} - {2*b:.2f}p$ ($/month per dollar of price)  
            **Critical Point:** $P'(p) = 0 \implies p^* = \mathbf{{\${p_unconstrained:.2f}}}$ (gives demand $q = {a - b*p_unconstrained:.1f}$ seats)
            """
        )
    elif level == "Applied":
        st.markdown(
            f"""
            **Business Question:** How does the monthly capacity cap ($s \le {cap:.0f}$ seats) change our optimal price?  
            **Constrained Sales Function:** $s(p) = \min({cap:.0f}, \max(0, {a:.1f} - {b:.2f}p))$ on $0 \le p \le {p_max:.2f}$  
            **Piecewise Derivative:**  
            - When $p < {p_cap_corner:.2f}$ (capacity-capped branch): $P'(p) = {cap:.0f}$ ($/month per dollar)  
            - When $p > {p_cap_corner:.2f}$ (demand-limited branch): $P'(p) = {a + b*v:.2f} - {2*b:.2f}p$  
            - At the capacity corner $p = \mathbf{{\${p_cap_corner:.2f}}}$: $P'(p)$ is **undefined** (sharp corner).
            """
        )
    else:  # Advanced
        st.markdown(
            """
            **Business Question:** Over a 10-day workshop promotion campaign ($0 \le t \le 10$ days), what is our net accumulated profit?  
            **Marginal Rate Functions (Adapter Fixture):**  
            - Revenue rate: $r(t) = 100 + 20t$ ($/day)  
            - Cost rate: $c(t) = 60 + 5t$ ($/day)  
            **Net Accumulation:** $\int_0^{10} (r(t) - c(t))\,dt = \$2,000 - \$850 = \mathbf{\$1,150.00}$  
            *(Note: Isolated campaign rate model; does not overwrite the monthly accounting ledger.)*
            """
        )

    # Interactive Transfer Check & Linked Plot
    st.divider()
    test_p = st.slider(
        "Transfer Check — Predict profit before moving the price slider ($p):",
        min_value=0.0,
        max_value=max(50.0, p_max),
        value=p0,
        step=0.5,
    )

    prices = np.linspace(0, p_max, 250)
    q_unconstrained = np.maximum(0.0, a - b * prices)
    p_profit_unconstrained = (prices - v) * q_unconstrained - F

    s_constrained = np.minimum(cap, q_unconstrained)
    p_profit_constrained = (prices - v) * s_constrained - F

    deriv_vals = np.where(prices < p_cap_corner, cap, a + b * v - 2 * b * prices)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    ax1.plot(prices, p_profit_unconstrained, "--", color="#6c757d", label="Unconstrained Profit P(p)")
    if level in ("Applied", "Advanced"):
        ax1.plot(prices, p_profit_constrained, "-", color="#0d6efd", linewidth=2, label=f"Constrained Profit (cap={cap:.0f})")
        if 0 <= p_cap_corner <= p_max:
            ax1.axvline(p_cap_corner, color="#d9534f", linestyle=":", label=f"Capacity Corner p=${p_cap_corner:.2f}")
    ax1.axhline(0, color="black", linewidth=0.8)
    ax1.axvline(test_p, color="#198754", linestyle="-.", label=f"Selected Price p=${test_p:.2f}")
    ax1.set_ylabel("Monthly Profit ($)")
    ax1.set_title(f"{PATHWAY_ID} Continuous Profit & Derivative Analysis ({level} Level)")
    ax1.legend(loc="best", fontsize=8)
    ax1.grid(True, alpha=0.3)

    ax2.plot(prices, deriv_vals if level != "Foundation" else (a + b * v - 2 * b * prices), color="#6610f2", label="P'(p) ($/month per $)")
    if level != "Foundation" and 0 <= p_cap_corner <= p_max:
        ax2.scatter([p_cap_corner], [cap], facecolors="none", edgecolors="#d9534f", s=60, zorder=5, label="Undefined Corner")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_xlabel("Workshop Seat Price p ($)")
    ax2.set_ylabel("Marginal Profit P'(p)")
    ax2.legend(loc="best", fontsize=8)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    st.pyplot(fig)

    # Discrete Integer Evaluation at Selected Price
    q_at_p = max(0.0, a - b * test_p)
    s_int = min(int(cap), math.floor(q_at_p))
    int_profit = (test_p - v) * s_int - F
    st.info(
        f"**Continuous vs. Integer Check at p = ${test_p:.2f}:** Continuous demand = {q_at_p:.2f} seats | "
        f"Rounded whole seats sold (capped at {int(cap)}) = **{s_int} seats** | "
        f"Actual integer operating profit = **${int_profit:,.2f}**"
    )

# =========================================================
# TAB 3: RUN SIMULATION & DATED LEDGER
# =========================================================
with tab_sim:
    st.subheader("Execute Monthly Simulation Step (Protected by Unique Run ID)")
    c_run1, c_run2, c_run3, c_run4 = st.columns(4)
    run_id = c_run1.text_input("Unique Run ID", value=f"RUN-{len(sim['ledger']) + 1:03d}")
    sim_date = c_run2.text_input("Period End Date (YYYY-MM-DD)", value="2027-01-31")
    req_demand = c_run3.number_input("Requested Seats", min_value=0, value=int(params["D0"]), step=1)
    ad_spend = c_run4.number_input("Approved Campaign Spend ($)", min_value=0.0, value=0.0, step=10.0)

    if st.button("Approve & Advance One Month"):
        if run_id in sim["processed_run_ids"]:
            st.warning(f"Duplicate Run Blocked: `{run_id}` has already been recorded. No duplicate transaction created.")
        else:
            res = run_monthly_step(requested=req_demand, p=params, ad_cost=money(ad_spend))
            new_cash = money(sim["cash"]) + res["cash_delta"]
            sim["cash"] = float(new_cash)
            sim["retained_earnings"] = float(money(sim["retained_earnings"]) + res["net_profit"])
            sim["state_version"] += 1
            sim["snapshot_id"] = f"SNAP-{sim['state_version']:03d}"
            sim["processed_run_ids"].append(run_id)

            sim["ledger"].append({
                "run_id": run_id,
                "date": sim_date,
                "state_version": sim["state_version"],
                "mode": "Normal",
                "requested": res["requested"],
                "booked": res["booked"],
                "attended_sold": res["sold"],
                "unserved_demand": res["unserved_demand"],
                "revenue": float(res["revenue"]),
                "variable_expense": float(res["variable_expense"]),
                "fixed_expense": float(res["fixed_expense"]),
                "ad_cost": float(res["ad_cost"]),
                "total_expense": float(res["total_expense"]),
                "profit": float(res["net_profit"]),
                "closing_cash": float(new_cash),
            })
            st.success(f"Recorded `{run_id}`! Advanced to state `v{sim['state_version']}`.")
            st.rerun()

    st.divider()
    st.subheader("Dated Simulation Ledger (Actual Transactions)")
    if sim["ledger"]:
        df_ledger = pd.DataFrame(sim["ledger"])
        st.dataframe(df_ledger, use_container_width=True)
        st.download_button(
            "Download Ledger CSV",
            data=df_ledger.to_csv(index=False),
            file_name=f"{sim['team_id']}_{PATHWAY_ID}_ledger.csv",
            mime="text/csv",
        )
    else:
        st.write("No simulated months recorded yet. Run a month above or execute the acceptance tests in Tab 4.")

# =========================================================
# TAB 4: STAGE 1 ACCEPTANCE TESTS (Handbook p. 60, 70, 85)
# =========================================================
with tab_tests:
    st.subheader("NUR-3 & AP Calculus Stage 1 Acceptance Tests")
    st.caption("Verifies exact handbook expected numbers before advancing to Stage 2.")

    if st.button("Run All Stage 1 Automated Checks"):
        results = []

        # Test 1: Zero Sales Check
        t_zero = run_monthly_step(requested=0, p=DEFAULTS)
        pass_zero = (t_zero["revenue"] == Decimal("0.00")) and (t_zero["net_profit"] == Decimal("-700.00"))
        results.append({
            "Test": "Zero Sales (requested=0)",
            "Expected": "Revenue=$0.00, Profit=-$700.00",
            "Actual": f"Revenue=${t_zero['revenue']}, Profit=${t_zero['net_profit']}",
            "Status": "PASS" if pass_zero else "FAIL",
        })

        # Test 2: Demand Exceeds Capacity (80 requested, 60 capacity)
        t_cap = run_monthly_step(requested=80, p=DEFAULTS)
        pass_cap = (t_cap["sold"] == 60) and (t_cap["unserved_demand"] == 20)
        results.append({
            "Test": "Demand Exceeds Capacity (80 vs 60)",
            "Expected": "Sold=60, Unserved=20",
            "Actual": f"Sold={t_cap['sold']}, Unserved={t_cap['unserved_demand']}",
            "Status": "PASS" if pass_cap else "FAIL",
        })

        # Test 3: NUR-3 Business-Specific No-Show Test (no_show_rate=0.20)
        p_noshow = dict(DEFAULTS)
        p_noshow["no_show_rate"] = 0.20
        t_noshow = run_monthly_step(requested=80, p=p_noshow)
        pass_noshow = (
            t_noshow["booked"] == 60
            and t_noshow["attended"] == 48
            and t_noshow["revenue"] == Decimal("1200.00")
            and t_noshow["variable_expense"] == Decimal("240.00")
            and t_noshow["net_profit"] == Decimal("260.00")
        )
        results.append({
            "Test": "NUR-3 No-Show Rate = 0.20 (Handbook p. 85)",
            "Expected": "Booked=60, Attended=48, Rev=$1,200, Var=$240, Profit=$260",
            "Actual": f"Booked={t_noshow['booked']}, Attended={t_noshow['attended']}, Rev=${t_noshow['revenue']}, Var=${t_noshow['variable_expense']}, Profit=${t_noshow['net_profit']}",
            "Status": "PASS" if pass_noshow else "FAIL",
        })

        # Test 4: 3-Month Fixture Replay (Handbook p. 85)
        cash_sim = Decimal("4000.00")
        expected_fixture = [
            ("2027-01", 60, Decimal("1500.00"), Decimal("1000.00"), Decimal("500.00"), Decimal("4500.00")),
            ("2027-02", 60, Decimal("1500.00"), Decimal("1100.00"), Decimal("400.00"), Decimal("4900.00")),
            ("2027-03", 45, Decimal("1125.00"), Decimal("925.00"), Decimal("200.00"), Decimal("5100.00")),
        ]
        fixture_ok = True
        actual_summary = []
        for idx, row in enumerate(MONTHLY_FIXTURE):
            out = run_monthly_step(
                requested=row["requested"],
                p=DEFAULTS,
                ad_cost=row["ad_cost"],
                capacity_override=row["capacity_override"],
            )
            cash_sim += out["cash_delta"]
            exp_m, exp_s, exp_r, exp_e, exp_p, exp_c = expected_fixture[idx]
            if not (
                out["sold"] == exp_s
                and out["revenue"] == exp_r
                and out["total_expense"] == exp_e
                and out["net_profit"] == exp_p
                and cash_sim == exp_c
            ):
                fixture_ok = False
            actual_summary.append(f"{exp_m}: sold={out['sold']}, profit=${out['net_profit']}, cash=${cash_sim}")

        results.append({
            "Test": "NUR-3 Monthly Fixture Replay (Jan-Mar 2027)",
            "Expected": "Jan cash=$4,500 | Feb cash=$4,900 | Mar cash=$5,100",
            "Actual": " | ".join(actual_summary),
            "Status": "PASS" if fixture_ok else "FAIL",
        })

        # Test 5: AP Calculus Adapter Fixture (D0=60, p0=30, v=10, F=500, cap=40 -> p*=40, profit=700)
        a_t, b_t = 2 * 60, 60 / 30
        p_corner_t = (a_t - 40) / b_t
        profit_t = (p_corner_t - 10) * 40 - 500
        pass_calc = (abs(p_corner_t - 40.0) < 1e-6) and (abs(profit_t - 700.0) < 1e-6)
        results.append({
            "Test": "AP Calculus Constrained Optimum Check (Handbook p. 70)",
            "Expected": "Constrained optimal price=$40.00, Profit=$700.00",
            "Actual": f"Optimal price=${p_corner_t:.2f}, Profit=${profit_t:.2f}",
            "Status": "PASS" if pass_calc else "FAIL",
        })

        st.table(pd.DataFrame(results))
