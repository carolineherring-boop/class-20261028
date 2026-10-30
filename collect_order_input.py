"""Collect and validate customer, product, and quantity for a new order."""

from order_entry import (
    create_supabase_client,
    display_customers,
    display_products,
    fetch_customers,
    fetch_products,
    run_order_workflow,
)


def main() -> None:
    client = create_supabase_client()
    customers = fetch_customers(client)
    products = fetch_products(client)

    if not customers or not products:
        print("Cannot collect an order: customers or products are missing.")
        return

    display_customers(customers)
    display_products(products)
    print("\nEnter an order using the IDs shown above.")
    run_order_workflow(client, customers, products)


if __name__ == "__main__":
    main()
