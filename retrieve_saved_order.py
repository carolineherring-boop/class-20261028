"""Retrieve a saved order from Supabase and display its stored values."""

from decimal import Decimal
from typing import Any

import httpx
from postgrest.exceptions import APIError
from supabase import Client


def _fetch_one(
    client: Client, table: str, columns: str, column: str, value: int
) -> dict[str, Any] | None:
    response = (
        client.table(table)
        .select(columns)
        .eq(column, value)
        .execute()
    )
    return response.data[0] if response.data else None


def retrieve_saved_order(
    client: Client, order_id: int
) -> dict[str, Any] | None:
    """Query Supabase for the order and its customer and product names."""
    order = _fetch_one(
        client,
        "orders",
        "order_id, customer_id, product_id, quantity, unit_price, order_date",
        "order_id",
        order_id,
    )
    if order is None:
        return None

    customer = _fetch_one(
        client, "customers", "name", "customer_id", order["customer_id"]
    )
    product = _fetch_one(
        client,
        "products",
        "product_name",
        "product_id",
        order["product_id"],
    )
    if customer is None or product is None:
        return None

    return {
        **order,
        "customer_name": customer["name"],
        "product_name": product["product_name"],
    }


def display_order_table(order: dict[str, Any]) -> None:
    unit_price = Decimal(str(order["unit_price"]))
    quantity = int(order["quantity"])
    total = unit_price * quantity
    values = [
        str(order["order_id"]),
        order["customer_name"],
        order["product_name"],
        str(quantity),
        f"${unit_price:.2f}",
        f"${total:.2f}",
        str(order["order_date"]),
    ]
    headers = [
        "Order ID",
        "Customer",
        "Product",
        "Quantity",
        "Unit Price",
        "Total",
        "Order Date",
    ]
    widths = [
        max(len(header), len(value))
        for header, value in zip(headers, values, strict=True)
    ]
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(values)))


def retrieve_and_display_order(client: Client, order_id: int) -> bool:
    """Verify an inserted order with a new query and display the database row."""
    order = retrieve_saved_order(client, order_id)
    if order is None:
        return False

    print("\nOrder saved and verified from Supabase:")
    display_order_table(order)
    return True


def main() -> None:
    try:
        order_id = int(input("Order ID to retrieve: ").strip())
    except ValueError:
        print("Enter a whole-number order ID.")
        return

    from order_entry import create_supabase_client

    try:
        if not retrieve_and_display_order(create_supabase_client(), order_id):
            print("Verification could not be completed: no matching order was found.")
    except (APIError, httpx.HTTPError):
        print(
            "Verification could not be completed. Check your connection and "
            "permissions, then try retrieving the order again."
        )


if __name__ == "__main__":
    main()
