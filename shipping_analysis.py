import pandas as pd
from shopify_reports import fetch_all_orders

INPUT_CSV = "expensereport.csv"
OUTPUT_XLSX = "shipping_analysis.xlsx"
BOX_COST = 1.0

# Load the expense report
exp = pd.read_csv(INPUT_CSV)

# Filter only shipping fees
ship = exp[exp["Product category"] == "shipping_fee"].copy()
ship["Created at"] = pd.to_datetime(ship["Created at"]).dt.tz_localize(None)
ship["month"] = ship["Created at"].dt.to_period("M")

# Total shipping cost
total_shipping_cost = ship["Billed amount"].sum()

# Shipping cost by month
ship_cost_by_month = ship.groupby("month")["Billed amount"].sum()

# Pull order data from Shopify to better estimate shipping revenue
orders = fetch_all_orders()
order_rows = []
for o in orders:
    shipping_price = sum(float(sl.get("price", 0.0)) for sl in o.get("shipping_lines", []))
    created = o.get("created_at")
    order_rows.append(
        {
            "order_id": o.get("id"),
            "created_at": pd.to_datetime(created).tz_localize(None),
            "shipping_price": shipping_price,
        }
    )

orders_df = pd.DataFrame(order_rows)
if not orders_df.empty:
    orders_df["month"] = orders_df["created_at"].dt.to_period("M")
    orders_df["box_fee"] = (orders_df["shipping_price"] > 0).astype(float) * BOX_COST
    orders_df["shipping_revenue"] = orders_df["shipping_price"] - orders_df["box_fee"]
else:
    orders_df = pd.DataFrame(columns=["order_id", "created_at", "shipping_price", "month", "box_fee", "shipping_revenue"])

shipping_revenue_est = orders_df["shipping_revenue"].sum()
free_shipping_orders = orders_df[orders_df["shipping_revenue"] == 0]
box_cost_free_shipping = len(free_shipping_orders[free_shipping_orders["shipping_price"] == 0]) * BOX_COST
free_shipping_cost_est = total_shipping_cost - shipping_revenue_est

summary_df = pd.DataFrame(
    {
        "total_shipping_cost": [total_shipping_cost],
        "estimated_shipping_revenue": [shipping_revenue_est],
        "estimated_free_shipping_cost": [free_shipping_cost_est],
        "box_cost_for_free_shipping": [box_cost_free_shipping],
    }
)

with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
    summary_df.to_excel(writer, index=False, sheet_name="Summary")
    ship_cost_by_month.to_frame(name="shipping_cost").to_excel(writer, sheet_name="MonthlyCost")
    orders_df.to_excel(writer, index=False, sheet_name="OrderShipping")
    ship.to_excel(writer, index=False, sheet_name="RawShipping")

print(f"Wrote shipping analysis to {OUTPUT_XLSX}")
