"""Streamlit customer-order app backed by Supabase."""

from decimal import Decimal
from typing import Any

import httpx
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from postgrest.exceptions import APIError
from supabase import Client, create_client

from order_entry import (
    create_order,
    create_supabase_client,
    fetch_customers,
    fetch_products,
)
from retrieve_saved_order import retrieve_saved_order


def _order_table_row(order: dict[str, Any]) -> dict[str, Any]:
    unit_price = Decimal(str(order["unit_price"]))
    quantity = int(order["quantity"])
    return {
        "Order ID": order["order_id"],
        "Customer": order["customer_name"],
        "Product": order["product_name"],
        "Quantity": quantity,
        "Unit Price": f"${unit_price:.2f}",
        "Total": f"${unit_price * quantity:.2f}",
        "Order Date": order["order_date"],
    }


def _create_app_client() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, StreamlitSecretNotFoundError):
        return create_supabase_client()

    return create_client(url, key)


def _verify_pending_order(client: Client) -> None:
    order_id = st.session_state.get("pending_order_id")
    if order_id is None:
        return

    try:
        order = retrieve_saved_order(client, order_id)
    except (APIError, httpx.HTTPError):
        st.warning(
            "The order was submitted, but verification could not be completed. "
            "Retry verification below; do not submit the order again."
        )
        return

    if order is None:
        st.warning(
            "The order was submitted, but no matching order was returned. "
            "Retry verification below; do not submit the order again."
        )
        return

    st.session_state["verified_order"] = order
    st.session_state["pending_order_id"] = None


def _render_order_form(
    client: Client,
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> None:
    if not customers or not products:
        st.error("Cannot create an order: customers or products are missing.")
        return

    customer_by_id = {int(row["customer_id"]): row for row in customers}
    product_by_id = {int(row["product_id"]): row for row in products}

    st.subheader("Customers")
    st.dataframe(
        [
            {"Customer ID": row["customer_id"], "Customer Name": row["name"]}
            for row in customers
        ],
        hide_index=True,
        width="stretch",
    )
    st.subheader("Products")
    st.dataframe(
        [
            {
                "Product ID": row["product_id"],
                "Product Name": row["product_name"],
                "Category": row["category"],
                "Current Price": f"${Decimal(str(row['price'])):.2f}",
            }
            for row in products
        ],
        hide_index=True,
        width="stretch",
    )

    customer_id = st.selectbox(
        "Customer",
        options=list(customer_by_id),
        format_func=lambda record_id: (
            f"{customer_by_id[record_id]['name']} (ID {record_id})"
        ),
    )
    product_id = st.selectbox(
        "Product",
        options=list(product_by_id),
        format_func=lambda record_id: (
            f"{product_by_id[record_id]['product_name']} "
            f"(${Decimal(str(product_by_id[record_id]['price'])):.2f})"
        ),
    )
    quantity = st.number_input("Quantity", min_value=1, step=1, value=1)

    customer = customer_by_id[customer_id]
    product = product_by_id[product_id]
    unit_price = Decimal(str(product["price"]))
    st.subheader("Order summary")
    st.write(f"**Customer:** {customer['name']}")
    st.write(f"**Product:** {product['product_name']}")
    st.write(f"**Quantity:** {quantity}")
    st.write(f"**Current unit price:** ${unit_price:.2f}")
    st.write(f"**Order total:** ${unit_price * quantity:.2f}")

    confirmed = st.checkbox("I confirm this purchase.")
    if st.button("Confirm and save order", type="primary", disabled=not confirmed):
        try:
            order_id = create_order(
                client,
                int(customer_id),
                int(product_id),
                int(quantity),
                product["price"],
            )
        except (APIError, httpx.HTTPError):
            st.error(
                "Supabase did not confirm the order submission. Check the "
                "connection and permissions before trying again."
            )
            return

        st.session_state["pending_order_id"] = order_id
        _verify_pending_order(client)
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Campus Store Orders")
    st.title("Campus Store Order Entry")
    st.caption(
        "Browse current customers and products, then create and verify a campus store order."
    )

    try:
        client = _create_app_client()
    except SystemExit:
        st.error(
            "Supabase credentials are missing. Add SUPABASE_URL and "
            "SUPABASE_KEY in Streamlit app Secrets, or use a local .env file."
        )
        st.stop()

    if st.session_state.get("pending_order_id") is not None:
        st.info(
            f"Order {st.session_state['pending_order_id']} was submitted. "
            "Complete verification before placing another order."
        )
        if st.button("Retry verification"):
            _verify_pending_order(client)
            st.rerun()
        return

    if st.button("Refresh Data"):
        st.session_state.pop("catalog_customers", None)
        st.session_state.pop("catalog_products", None)
        st.rerun()

    if (
        "catalog_customers" not in st.session_state
        or "catalog_products" not in st.session_state
    ):
        try:
            st.session_state["catalog_customers"] = fetch_customers(client)
            st.session_state["catalog_products"] = fetch_products(client)
        except (APIError, httpx.HTTPError):
            st.error(
                "Could not load customers and products from Supabase. "
                "Check the connection and database permissions."
            )
            return

    customers = st.session_state["catalog_customers"]
    products = st.session_state["catalog_products"]

    _render_order_form(client, customers, products)

    verified_order = st.session_state.get("verified_order")
    if verified_order:
        st.success(f"Order {verified_order['order_id']} was saved and verified.")
        st.subheader("Order retrieved from Supabase")
        st.dataframe(
            [_order_table_row(verified_order)],
            hide_index=True,
            width="stretch",
        )


if __name__ == "__main__":
    main()
