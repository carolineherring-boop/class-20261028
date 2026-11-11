"""Display customers and products stored in the class Supabase project."""

import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from postgrest.exceptions import APIError
from dotenv import load_dotenv
from supabase import Client, create_client

from order_validation import (
    ask_for_confirmation,
    ask_for_existing_id,
    ask_for_quantity,
)
from retrieve_saved_order import retrieve_and_display_order


def fetch_customers(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("customers")
        .select("customer_id, name")
        .order("customer_id")
        .execute()
    )
    return response.data


def fetch_products(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("products")
        .select("product_id, product_name, category, price")
        .order("product_id")
        .execute()
    )
    return response.data


def fetch_customer(client: Client, customer_id: int) -> dict[str, Any] | None:
    """Return one customer from Supabase, or None if it no longer exists."""
    response = (
        client.table("customers")
        .select("customer_id, name")
        .eq("customer_id", customer_id)
        .execute()
    )
    return response.data[0] if response.data else None


def fetch_product(client: Client, product_id: int) -> dict[str, Any] | None:
    """Return one product with its current price, or None if it does not exist."""
    response = (
        client.table("products")
        .select("product_id, product_name, category, price")
        .eq("product_id", product_id)
        .execute()
    )
    return response.data[0] if response.data else None


def fetch_order_history(client: Client) -> list[dict[str, Any]]:
    """Return saved orders, newest first."""
    response = (
        client.table("orders")
        .select("order_id, customer_id, product_id, quantity, unit_price, order_date")
        .order("order_id", desc=True)
        .execute()
    )
    return response.data


def create_supabase_client() -> Client:
    """Create a client from credentials in the local .env file."""
    load_dotenv(Path(__file__).with_name(".env"))
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise SystemExit(
            "Missing Supabase credentials. Copy .env.example to .env and "
            "fill in SUPABASE_URL and SUPABASE_KEY."
        )

    return create_client(url, key)


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print rows in a simple, readable, column-aligned table."""
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    separator = "-+-".join("-" * width for width in widths)

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print(separator)
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def display_customers(customers: list[dict[str, Any]]) -> None:
    rows = [
        [str(customer["customer_id"]), customer["name"]]
        for customer in customers
    ]

    print("Customers")
    print_table(["Customer ID", "Customer Name"], rows)


def display_products(products: list[dict[str, Any]]) -> None:
    rows = [
        [
            str(product["product_id"]),
            product["product_name"],
            f"${Decimal(str(product['price'])):.2f}",
        ]
        for product in products
    ]

    print("\nProducts")
    print_table(["Product ID", "Product Name", "Price"], rows)


def create_order(
    client: Client,
    customer_id: int,
    product_id: int,
    quantity: int,
    unit_price: Any,
) -> int:
    insert_response = (
        client.table("orders")
        .insert(
            {
                "customer_id": customer_id,
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "order_date": date.today().isoformat(),
            }
        )
        .select("order_id")
        .single()
        .execute()
    )
    return insert_response.data["order_id"]


def display_order_summary(
    customer: dict[str, Any], product: dict[str, Any], quantity: int
) -> None:
    unit_price = Decimal(str(product["price"]))
    order_total = quantity * unit_price
    print("\nOrder summary")
    print(f"Customer:     {customer['name']}")
    print(f"Product:      {product['product_name']}")
    print(f"Quantity:     {quantity}")
    print(f"Current price: ${unit_price:.2f}")
    print(f"Order total:  ${order_total:.2f}")


def run_order_workflow(
    client: Client,
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> None:
    if not customers or not products:
        print("\nCannot enter an order: customers or products are missing.")
        return

    customer_ids = {customer["customer_id"] for customer in customers}
    customers_by_id = {customer["customer_id"]: customer for customer in customers}
    products_by_id = {product["product_id"]: product for product in products}
    customer_id = ask_for_existing_id(
        "\nCustomer ID: ", customer_ids, "customer"
    )
    product_id = ask_for_existing_id(
        "Product ID: ", set(products_by_id), "product"
    )
    quantity = ask_for_quantity()

    customer = customers_by_id[customer_id]
    product = products_by_id[product_id]
    display_order_summary(customer, product, quantity)
    if not ask_for_confirmation():
        print("Order canceled. Nothing was saved.")
        return

    try:
        order_id = create_order(
            client,
            customer_id,
            product_id,
            quantity,
            product["price"],
        )
    except (APIError, httpx.HTTPError):
        print(
            "The order could not be confirmed as submitted. Check your "
            "connection, permissions, and the orders table before retrying."
        )
        return

    try:
        verified = retrieve_and_display_order(client, order_id)
    except (APIError, httpx.HTTPError):
        print(
            "The order was submitted, but verification could not be completed. "
            "Check Supabase before retrying; the order was not inserted again."
        )
        return

    if not verified:
        print(
            "The order was submitted, but no matching order was returned for "
            "verification. Check Supabase before retrying; the order was not "
            "inserted again."
        )


def main() -> None:
    client = create_supabase_client()
    customers = fetch_customers(client)
    products = fetch_products(client)
    display_customers(customers)
    display_products(products)
    run_order_workflow(client, customers, products)


if __name__ == "__main__":
    main()
