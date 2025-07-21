# Basic Shopify lifetime reports generator

import os
import requests
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime
import pandas as pd

load_dotenv()

SHOPIFY_STORE_NAME = os.getenv("SHOPIFY_STORE_NAME")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2024-01")
SHOPIFY_ADMIN_API_ACCESS_TOKEN = os.getenv("SHOPIFY_ADMIN_API_ACCESS_TOKEN")


def get_shopify_headers():
    if not SHOPIFY_ADMIN_API_ACCESS_TOKEN:
        raise ValueError("SHOPIFY_ADMIN_API_ACCESS_TOKEN not found in environment variables.")
    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ADMIN_API_ACCESS_TOKEN,
    }


def build_shopify_url(endpoint: str) -> str:
    if not SHOPIFY_STORE_NAME or not SHOPIFY_API_VERSION:
        raise ValueError("SHOPIFY_STORE_NAME or SHOPIFY_API_VERSION not found in environment variables.")
    return f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/{endpoint}"


def fetch_all_orders() -> list[dict]:
    orders = []
    endpoint = (
        "orders.json?status=any&limit=250&fields=id,created_at,total_price,total_discounts,subtotal_price,shipping_lines,line_items"
    )
    headers = get_shopify_headers()
    while endpoint:
        url = build_shopify_url(endpoint)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json().get("orders", [])
        orders.extend(data)
        link_header = response.headers.get("Link")
        endpoint = None
        if link_header:
            links = link_header.split(",")
            for link in links:
                parts = link.split(";")
                if 'rel="next"' in parts[1]:
                    next_url = parts[0].strip()[1:-1]
                    endpoint = next_url.split(f"/admin/api/{SHOPIFY_API_VERSION}/")[-1]
                    break
    return orders


def fetch_all_products() -> dict:
    products = {}
    endpoint = "products.json?limit=250&fields=id,title,variants"
    headers = get_shopify_headers()
    while endpoint:
        url = build_shopify_url(endpoint)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json().get("products", [])
        for product in data:
            products[product["id"]] = product
        link_header = response.headers.get("Link")
        endpoint = None
        if link_header:
            links = link_header.split(",")
            for link in links:
                parts = link.split(";")
                if 'rel="next"' in parts[1]:
                    next_url = parts[0].strip()[1:-1]
                    endpoint = next_url.split(f"/admin/api/{SHOPIFY_API_VERSION}/")[-1]
                    break
    return products


def collect_metrics(orders: list[dict], products: dict) -> dict:
    shipping_paid_by_customers = 0.0
    shipping_cost_to_us = 0.0
    free_shipping_cost = 0.0
    product_revenue = defaultdict(float)
    order_shipping_rows = []

    for order in orders:
        created = order.get("created_at")
        order_id = order.get("id")
        lines = order.get("shipping_lines", [])
        total_paid_shipping = 0.0
        total_cost_shipping = 0.0
        for sl in lines:
            price = float(sl.get("price", 0.0))
            cost = float(sl.get("original_price", sl.get("price", 0.0)))
            total_paid_shipping += price
            total_cost_shipping += cost
            if price == 0:
                free_shipping_cost += cost
        shipping_paid_by_customers += total_paid_shipping
        shipping_cost_to_us += total_cost_shipping
        order_shipping_rows.append({
            "order_id": order_id,
            "created_at": created,
            "shipping_paid_by_customer": total_paid_shipping,
            "shipping_cost": total_cost_shipping,
            "shipping_discount": total_cost_shipping - total_paid_shipping,
        })

        for item in order.get("line_items", []):
            product_id = item.get("product_id")
            quantity = item.get("quantity", 0)
            price = float(item.get("price", 0.0))
            product_revenue[product_id] += price * quantity

    sold_out_product_revenue = {}
    for pid, pdata in products.items():
        all_oos = True
        for variant in pdata.get("variants", []):
            if variant.get("inventory_quantity", 0) > 0:
                all_oos = False
                break
        if all_oos:
            sold_out_product_revenue[pdata["title"]] = product_revenue.get(pid, 0.0)

    summary = {
        "total_orders": len(orders),
        "total_revenue": sum(float(o.get("total_price", 0.0)) for o in orders),
        "total_discounts": sum(float(o.get("total_discounts", 0.0)) for o in orders),
        "shipping_paid_by_customers": shipping_paid_by_customers,
        "shipping_cost": shipping_cost_to_us,
        "shipping_paid_for_free": free_shipping_cost,
        "shipping_profit_or_loss": shipping_paid_by_customers - shipping_cost_to_us,
        "average_order_value": (sum(float(o.get("total_price", 0.0)) for o in orders) / len(orders)) if orders else 0.0,
    }

    product_revenue_named = {
        products[pid]["title"] if pid in products else str(pid): rev
        for pid, rev in product_revenue.items()
    }

    return {
        "summary": summary,
        "shipping_rows": order_shipping_rows,
        "sold_out_product_revenue": sold_out_product_revenue,
        "product_revenue": product_revenue_named,
    }


def write_excel_report(metrics: dict, filename: str):
    summary_df = pd.DataFrame([metrics["summary"]])
    shipping_df = pd.DataFrame(metrics["shipping_rows"])
    sold_out_df = (
        pd.DataFrame(list(metrics["sold_out_product_revenue"].items()), columns=["product", "revenue"])
        if metrics["sold_out_product_revenue"]
        else pd.DataFrame(columns=["product", "revenue"])
    )
    product_rev_df = pd.DataFrame(list(metrics["product_revenue"].items()), columns=["product", "revenue"])

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        shipping_df.to_excel(writer, index=False, sheet_name="Shipping")
        sold_out_df.to_excel(writer, index=False, sheet_name="SoldOutProducts")
        product_rev_df.to_excel(writer, index=False, sheet_name="ProductRevenue")


def main():
    orders = fetch_all_orders()
    products = fetch_all_products()
    metrics = collect_metrics(orders, products)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"shopify_report_{timestamp}.xlsx"
    write_excel_report(metrics, filename)
    print(f"Report written to {filename}")


if __name__ == "__main__":
    main()
