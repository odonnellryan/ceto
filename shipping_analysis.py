import pandas as pd

INPUT_CSV = "expensereport.csv"
OUTPUT_XLSX = "shipping_analysis.xlsx"

# Load the expense report
exp = pd.read_csv(INPUT_CSV)

# Filter only shipping fees
ship = exp[exp["Product category"] == "shipping_fee"].copy()
ship["Created at"] = pd.to_datetime(ship["Created at"])
ship["month"] = ship["Created at"].dt.to_period("M")

# Total shipping cost
total_shipping_cost = ship["Billed amount"].sum()

# Shipping cost by month
ship_cost_by_month = ship.groupby("month")["Billed amount"].sum()

# Categorize shipping fees using simple heuristics
# <1     -> refunds/adjustments
# 1-6    -> charged to customer (domestic < $50 orders)
# 6-10   -> free shipping (domestic > $50 orders)
# >=10   -> charged to customer (international orders)
category_labels = ["refund", "charged_domestic", "free_domestic", "charged_international"]
ship["category"] = pd.cut(
    ship["Billed amount"],
    bins=[-1, 1, 6, 10, float("inf")],
    labels=category_labels,
)

category_totals = ship.groupby("category")["Billed amount"].agg(["count", "sum"])

# Estimate shipping revenue (customer paid shipping) for charged categories
shipping_revenue_est = (
    category_totals.loc["charged_domestic", "sum"]
    + category_totals.loc["charged_international", "sum"]
)
# Cost of free shipping is the total of the free_domestic category
free_shipping_cost_est = category_totals.loc["free_domestic", "sum"]

summary_df = pd.DataFrame(
    {
        "total_shipping_cost": [total_shipping_cost],
        "estimated_shipping_revenue": [shipping_revenue_est],
        "estimated_free_shipping_cost": [free_shipping_cost_est],
    }
)

with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
    summary_df.to_excel(writer, index=False, sheet_name="Summary")
    ship_cost_by_month.to_frame(name="shipping_cost").to_excel(writer, sheet_name="MonthlyCost")
    category_totals.to_excel(writer, sheet_name="CategorySummary")
    ship.to_excel(writer, index=False, sheet_name="RawShipping")

print(f"Wrote shipping analysis to {OUTPUT_XLSX}")
