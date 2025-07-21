import os
import re
from collections import defaultdict

import requests
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_STORE_NAME = os.getenv("SHOPIFY_STORE_NAME")
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_ADMIN_API_ACCESS_TOKEN = os.getenv("SHOPIFY_ADMIN_API_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2024-01")

USER_SKIP_COMMAND = "skip"

LBS_TO_GRAMS_CONVERSION = 453.59237
ROAST_LOSS_PERCENTAGE = 0.15
ROAST_YIELD_FACTOR = 1.0 - ROAST_LOSS_PERCENTAGE


def get_shopify_headers():
    if not SHOPIFY_ADMIN_API_ACCESS_TOKEN:
        raise ValueError("SHOPIFY_ADMIN_API_ACCESS_TOKEN not found in environment variables.")
    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ADMIN_API_ACCESS_TOKEN,
    }


def build_shopify_url(endpoint):
    if not SHOPIFY_STORE_NAME or not SHOPIFY_API_VERSION:
        raise ValueError("SHOPIFY_STORE_NAME or SHOPIFY_API_VERSION not found in environment variables.")
    return f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/{endpoint}"


def parse_weight_from_title(title_string):
    """
    Attempts to parse weight in grams from a string (e.g., variant title).
    Returns (grams, unit_type_parsed) or (None, None) if not found.
    Unit types: 'g', 'kg', 'lb', 'oz'.
    """
    if not title_string:
        return None, None
    title_lower = title_string.lower()

    match_kg = re.search(r'(\d+\.?\d*)\s*(?:kg|kilogram|kilograms)\b', title_lower)
    if match_kg:
        try:
            return float(match_kg.group(1)) * 1000, 'kg'
        except ValueError:
            pass

    match_lb = re.search(r'(\d+\.?\d*)\s*(?:lb|lbs|pound|pounds)\b', title_lower)
    if match_lb:
        try:
            return float(match_lb.group(1)) * 453.59237, 'lb'
        except ValueError:
            pass

    match_oz = re.search(r'(\d+\.?\d*)\s*(?:oz|ounce|ounces)\b', title_lower)
    if match_oz:
        try:
            return float(match_oz.group(1)) * 28.3495, 'oz'
        except ValueError:
            pass

    match_g = re.search(r'(\d+\.?\d*)\s*(?:g|gram|grams)(?![a-zA-Z])', title_lower)
    if match_g:
        try:
            return float(match_g.group(1)), 'g'
        except ValueError:
            pass

    return None, None

def fetch_and_structure_products():
    structured_products = {}
    endpoint = "products.json?limit=250&fields=id,title,variants"
    headers = get_shopify_headers()
    page_count = 0
    while endpoint:
        page_count += 1
        relative_endpoint = endpoint.split(f'/admin/api/{SHOPIFY_API_VERSION}/')[-1]
        url = build_shopify_url(relative_endpoint)
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            products_on_page = data.get("products", [])
            if not products_on_page: break
            for product_data in products_on_page:
                product_id = product_data['id']
                product_title = product_data['title']
                variants_dict = {}
                for variant_data in product_data.get("variants", []):
                    grams, unit = parse_weight_from_title(variant_data['title'])
                    variants_dict[variant_data['id']] = {
                        'variant_id': variant_data['id'],
                        'variant_title': variant_data['title'],
                        'sku': variant_data.get('sku', 'N/A'),
                        'grams_per_item': grams,
                        'parsed_unit_type': unit,
                        'inventory_quantity': variant_data.get('inventory_quantity', 0),
                        'inventory_policy': variant_data.get('inventory_policy', 'deny')
                    }
                structured_products[product_id] = {
                    'product_id': product_id,
                    'product_title': product_title,
                    'variants': variants_dict
                }
            link_header = response.headers.get("Link")
            endpoint = None
            if link_header:
                links = link_header.split(',')
                for link in links:
                    parts = link.split(';')
                    if 'rel="next"' in parts[1]:
                        next_url = parts[0].strip()[1:-1]
                        endpoint = next_url.split(f'/admin/api/{SHOPIFY_API_VERSION}/')[-1]
                        break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching products: {e}")
            if hasattr(e, 'response') and e.response is not None: print(f"Response content: {e.response.text}")
            return None
        except ValueError as e:
            print(f"Error decoding JSON for products: {e}")
            return None
    return structured_products


def fetch_unfulfilled_order_quantities(all_variant_ids):
    unfulfilled_quantities = defaultdict(int)
    endpoint = "orders.json?status=open&limit=250&fields=id,line_items"
    headers = get_shopify_headers()
    page_count = 0
    while endpoint:
        page_count += 1
        relative_endpoint = endpoint.split(f'/admin/api/{SHOPIFY_API_VERSION}/')[-1]
        url = build_shopify_url(relative_endpoint)
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            orders_on_page = data.get("orders", [])
            if not orders_on_page: break
            for order in orders_on_page:
                for item in order.get("line_items", []):
                    variant_id = item.get("variant_id")
                    fulfillable_quantity = item.get("fulfillable_quantity", 0)
                    if variant_id and variant_id in all_variant_ids and fulfillable_quantity > 0:
                        unfulfilled_quantities[variant_id] += fulfillable_quantity
            link_header = response.headers.get("Link")
            endpoint = None
            if link_header:
                links = link_header.split(',')
                for link in links:
                    parts = link.split(';')
                    if 'rel="next"' in parts[1]:
                        next_url = parts[0].strip()[1:-1]
                        endpoint = next_url.split(f'/admin/api/{SHOPIFY_API_VERSION}/')[-1]
                        break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching orders: {e}")
            if hasattr(e, 'response') and e.response is not None: print(f"Response content: {e.response.text}")
            return None
        except ValueError as e:
            print(f"Error decoding JSON for orders: {e}")
            return None
    return unfulfilled_quantities


def fetch_latest_fulfilled_batch_quantities(all_variant_ids):
    """If no open orders are found, return quantities from the most recent
    fulfillment batch. All orders that share the same fulfillment date are
    aggregated together."""

    batch_quantities = defaultdict(int)
    endpoint = (
        "orders.json?status=any&limit=250&fields=id,line_items,fulfillments"
    )
    headers = get_shopify_headers()
    fulfillments_by_date = defaultdict(list)

    while endpoint:
        relative_endpoint = endpoint.split(
            f"/admin/api/{SHOPIFY_API_VERSION}/"
        )[-1]
        url = build_shopify_url(relative_endpoint)
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            orders_on_page = data.get("orders", [])
            if not orders_on_page:
                break
            for order in orders_on_page:
                fulfillments = order.get("fulfillments", [])
                if not fulfillments:
                    continue
                created_at = fulfillments[0].get("created_at")
                if not created_at:
                    continue
                date_key = created_at[:10]
                fulfillments_by_date[date_key].append(order)

            link_header = response.headers.get("Link")
            endpoint = None
            if link_header:
                links = link_header.split(',')
                for link in links:
                    parts = link.split(';')
                    if 'rel="next"' in parts[1]:
                        next_url = parts[0].strip()[1:-1]
                        endpoint = next_url.split(
                            f"/admin/api/{SHOPIFY_API_VERSION}/"
                        )[-1]
                        break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching fulfilled orders: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return None
        except ValueError as e:
            print(f"Error decoding JSON for fulfilled orders: {e}")
            return None

    if not fulfillments_by_date:
        return batch_quantities

    latest_date = max(fulfillments_by_date.keys())

    for order in fulfillments_by_date[latest_date]:
        for item in order.get("line_items", []):
            variant_id = item.get("variant_id")
            qty = item.get("quantity", 0)
            if variant_id and variant_id in all_variant_ids and qty > 0:
                batch_quantities[variant_id] += qty

    return batch_quantities


def get_int_input(prompt_message, default_value=0):
    while True:
        val_str = input(prompt_message).strip()
        if val_str.lower() == "skip": return USER_SKIP_COMMAND
        if not val_str: return default_value
        try:
            val = int(val_str)
            if val < 0:
                print("    Value cannot be negative. Please try again.")
                continue
            return val
        except ValueError:
            print(
                f"    Invalid input. Please enter 'skip', a whole number, or press Enter for default ({default_value}).")


def get_float_input(prompt_message, default_value=0.0):
    while True:
        val_str = input(prompt_message).strip()
        if val_str.lower() == "skip":
            return USER_SKIP_COMMAND
        if not val_str:
            return default_value
        try:
            val = float(val_str)
            if val < 0:
                print("    Value cannot be negative. Please try again.")
                continue
            return val
        except ValueError:
            print(f"    Invalid input. Please enter 'skip', a number, or press Enter for default ({default_value}).")


if __name__ == "__main__":

    if not all([SHOPIFY_STORE_NAME, SHOPIFY_API_KEY, SHOPIFY_ADMIN_API_ACCESS_TOKEN, SHOPIFY_API_VERSION]):
        print("Error: Shopify configuration is missing. Please check your .env file.")
        exit()


    all_products_data = fetch_and_structure_products()
    if not all_products_data:
        print("Could not retrieve product data. Exiting.")
        exit()

    all_variant_ids_from_products = {vid for pid in all_products_data for vid in all_products_data[pid]['variants']}
    if not all_variant_ids_from_products:
        print("No variants found. Exiting.")
        exit()

    shopify_unfulfilled_quantities = fetch_unfulfilled_order_quantities(all_variant_ids_from_products)
    if shopify_unfulfilled_quantities is None:
        print("Could not retrieve order quantities. Exiting.")
        exit()
    if not shopify_unfulfilled_quantities:
        print("No open orders found. Checking latest fulfillment batch...")
        shopify_unfulfilled_quantities = fetch_latest_fulfilled_batch_quantities(
            all_variant_ids_from_products
        )
        if shopify_unfulfilled_quantities is None:
            print("Could not retrieve fulfilled order quantities. Exiting.")
            exit()
        if not shopify_unfulfilled_quantities:
            print("No fulfilled orders found to use for roast calculations.")
            exit()

    roast_plan_data = {}

    for product_id, product_info in all_products_data.items():
        product_title = product_info['product_title']

        total_unfulfilled_for_product = 0
        all_variants_out_of_stock = True
        if not product_info['variants']:
            all_variants_out_of_stock = True
        else:
            for variant_id, variant_details in product_info['variants'].items():
                total_unfulfilled_for_product += shopify_unfulfilled_quantities.get(variant_id, 0)
                if variant_details.get('inventory_quantity', 0) > 0:
                    all_variants_out_of_stock = False

        if total_unfulfilled_for_product == 0 and all_variants_out_of_stock:
            continue

        current_product_roast_details = {
            'product_title': product_title,
            'variant_needs': {},
            'additional_wholesale_lbs_manual': 0.0,
            '8oz_wholesale': 0.0,
            '16oz_wholesale': 0.0,
        }

        if not product_info['variants']:
            print("  No variants defined for this product in Shopify. Skipping prompts for variants.")
        else:
            for variant_id, variant_details in product_info['variants'].items():
                variant_title = variant_details['variant_title']
                grams_per_item = variant_details['grams_per_item']
                if not grams_per_item:
                    grams_per_item = 115
                    variant_title = '115g'
                parsed_unit_display = f"" if grams_per_item else "(weight not parsed)"

                shopify_qty = shopify_unfulfilled_quantities.get(variant_id, 0)

                if grams_per_item is None:
                    print(f"    WARNING: Weight for variant '{variant_title}' could not be automatically parsed.")
                    while True:
                        manual_grams_str = input(
                            f"    Enter weight in GRAMS for one unit of '{variant_title}' (or 'skip' this product, or Enter to skip variant for calcs): ").strip()
                        if not manual_grams_str:
                            grams_per_item = None
                            print(f"    Skipping quantity calculations for '{variant_title}' due to missing weight.")
                            break
                        try:
                            grams_per_item = float(manual_grams_str)
                            if grams_per_item <= 0:
                                print("    Weight must be positive.")
                                grams_per_item = None
                                continue
                            variant_details['grams_per_item'] = grams_per_item  # Update original structure too
                            print(f"    Using manually entered weight: {grams_per_item:.2f}g")
                            break
                        except ValueError:
                            print("    Invalid input.")

                sample_qty_units = 0
                cafe_qty_units = 0

                current_product_roast_details['variant_needs'][variant_id] = {
                    'variant_title': variant_title,
                    'grams_per_item': grams_per_item,
                    'shopify_order_qty': shopify_qty,
                    'sample_qty_units': sample_qty_units,
                    'cafe_qty_units': cafe_qty_units
                }

        roast_plan_data[product_id] = current_product_roast_details

    # --- Calculations and Final Output ---
    print("\n\n--- FINAL ROASTING CALCULATIONS ---")

    print(f"(Assuming {ROAST_LOSS_PERCENTAGE * 100:.0f}% roasting loss)")

    print("\n\nProduct\tRoasted Needed")

    total_bags = 0

    if not roast_plan_data:
        print("No products were selected or had demand for roasting.")
    else:
        for product_id, data in roast_plan_data.items():
            product_title = data['product_title']
            total_roasted_grams_for_product = 0.0

            for v_id, v_data in data['variant_needs'].items():
                grams_per_item = v_data['grams_per_item']
                if grams_per_item and grams_per_item > 0:
                    total_units = v_data['shopify_order_qty'] + v_data['sample_qty_units'] + v_data['cafe_qty_units']
                    if grams_per_item > 50:
                        total_bags += total_units
                    # add some buffer as we always put in at least five extra grams on average, and toss some away
                    if total_units:
                        total_roasted_grams_for_product += total_units * grams_per_item + 8
                elif v_data['shopify_order_qty'] > 0 or v_data['sample_qty_units'] > 0 or v_data['cafe_qty_units'] > 0:
                    # Only warn if there were quantities but no weight
                    print(
                        f"  WARNING: Cannot calculate gram needs for variant '{v_data['variant_title']}' of '{product_title}' due to missing weight per item.")

            data['total_roasted_grams_product'] = total_roasted_grams_for_product

            print(f"{product_title}\t{total_roasted_grams_for_product:,.2f}")
        print(f"\n\nTotal bags: {total_bags}")
        print(f"\n\n--- Label Needs --- DOES NOT INCLUDE WHOLESALE ---")
        for product in roast_plan_data.values():
            hit_first = False
            for variant_id, variant_data in product['variant_needs'].items():
                if variant_id == 'wholesale_lbs':
                    continue
                if not hit_first:
                    hit_first = True
                    print(f"\n{product['product_title']}")
                if not any([variant_data['shopify_order_qty'], variant_data['sample_qty_units'], variant_data['cafe_qty_units']]):
                    continue
                print(
                    f"{variant_data['shopify_order_qty'] + variant_data['sample_qty_units'] + variant_data['cafe_qty_units']} X {variant_data['variant_title']}")

        # print(f"\n\n--- Orders ---")
        # for product in roast_plan_data.values():
        #     hit_first = False
        #     for variant_id, variant_data in product['variant_needs'].items():
        #         if not hit_first:
        #             hit_first = True
        #             print(f"\n{product['product_title']}")
        #         if not any([variant_data['shopify_order_qty'], variant_data['sample_qty_units'], variant_data['cafe_qty_units']]):
        #             continue
        #         if variant_data['shopify_order_qty']:
        #             print(f"Shopify {variant_data['variant_title']}: {variant_data['shopify_order_qty']}")
        #         if variant_data['sample_qty_units']:
        #             print(f"Samples {variant_data['variant_title']}: {variant_data['sample_qty_units']}")
        #         if variant_data['cafe_qty_units']:
        #             print(f"Cafe {variant_data['variant_title']}: {variant_data['cafe_qty_units']}")

