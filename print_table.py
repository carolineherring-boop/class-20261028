"""Fetch and display customers and products in readable terminal tables."""

from order_entry import (
    create_supabase_client,
    display_customers,
    display_products,
    fetch_customers,
    fetch_products,
)


def main() -> None:
    client = create_supabase_client()
    customers = fetch_customers(client)
    products = fetch_products(client)

    display_customers(customers)
    display_products(products)


if __name__ == "__main__":
    main()
