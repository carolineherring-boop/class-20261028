"""Streamlit customer-order app backed by Supabase."""

import hmac
import os
from decimal import Decimal
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from streamlit.errors import StreamlitSecretNotFoundError
from supabase import Client, create_client

from order_entry import (
    create_order,
    create_supabase_client,
    fetch_customer,
    fetch_customers,
    fetch_order_history,
    fetch_product,
    fetch_products,
)
from order_validation import validate_quantity
from retrieve_saved_order import retrieve_saved_order

DB_ERRORS = (APIError, httpx.HTTPError)


def _money(value: Any) -> str:
    return f"${Decimal(str(value)):,.2f}"


def _get_setting(name: str) -> str | None:
    """Read a setting from Streamlit secrets, falling back to the local .env file."""
    try:
        value = st.secrets[name]
    except (KeyError, StreamlitSecretNotFoundError):
        load_dotenv()
        value = os.getenv(name)
    return str(value) if value else None


# --------------------------------------------------------------------------
# Access control
# --------------------------------------------------------------------------
def _require_password() -> None:
    """Stop the script unless the user entered the app password from secrets.

    This runs before any Supabase client is created, so unauthenticated
    visitors never trigger a database request.
    """
    if st.session_state.get("authenticated"):
        return

    expected = _get_setting("APP_PASSWORD")
    if not expected:
        st.error(
            "This app is locked because no APP_PASSWORD is configured. "
            "Add APP_PASSWORD to the deployment secrets."
        )
        st.stop()

    st.title("Campus Store Order Entry")
    with st.form("login"):
        password = st.text_input("App password", type="password")
        submitted = st.form_submit_button("Enter")
    if submitted:
        if hmac.compare_digest(password.encode(), expected.encode()):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()


def _create_app_client() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, StreamlitSecretNotFoundError):
        return create_supabase_client()
    return create_client(url, key)


# --------------------------------------------------------------------------
# Data loading (cached in session state; cleared by Refresh Data / insert)
# --------------------------------------------------------------------------
def _describe_error(error: Exception) -> str:
    """Return a short, credential-free explanation of a Supabase error."""
    if isinstance(error, APIError):
        parts = [error.message or "", f"(code {error.code})" if error.code else ""]
        if error.hint:
            parts.append(f"Hint: {error.hint}")
        return " ".join(p for p in parts if p).strip() or "Unknown API error"
    if isinstance(error, httpx.ConnectError):
        return "Could not connect. Check that SUPABASE_URL is correct."
    return type(error).__name__


def _load_data(client: Client) -> bool:
    loaders = {
        "customers": fetch_customers,
        "products": fetch_products,
        "order_history": fetch_order_history,
    }
    for key, loader in loaders.items():
        if key in st.session_state:
            continue
        try:
            st.session_state[key] = loader(client)
        except DB_ERRORS as error:
            table = "orders" if key == "order_history" else key
            st.error(
                f"Could not load the **{table}** table from Supabase: "
                f"{_describe_error(error)}. Check the app secrets and the table, "
                "then select Refresh Data."
            )
            return False
    return True


def _clear_cached_data() -> None:
    for key in ("customers", "products", "order_history"):
        st.session_state.pop(key, None)


# --------------------------------------------------------------------------
# Section 1: display customers and products
# --------------------------------------------------------------------------
def _render_catalog(customers: list[dict], products: list[dict]) -> None:
    left, right = st.columns(2)
    with left:
        st.subheader("Customers")
        st.dataframe(
            [
                {"Customer ID": row["customer_id"], "Customer Name": row["name"]}
                for row in customers
            ],
            hide_index=True,
            width="stretch",
        )
    with right:
        st.subheader("Products")
        st.dataframe(
            [
                {
                    "Product ID": row["product_id"],
                    "Product Name": row["product_name"],
                    "Category": row["category"],
                    "Price": _money(row["price"]),
                }
                for row in products
            ],
            hide_index=True,
            width="stretch",
        )


# --------------------------------------------------------------------------
# Sections 2 & 3: order entry, validation, and saving
# --------------------------------------------------------------------------
def _submit_order(
    client: Client, customer_id: int, product_id: int, quantity: int, reviewed_price: Decimal
) -> None:
    """Validate against Supabase, insert once, then verify with a new query."""
    try:
        quantity = validate_quantity(str(quantity))
    except ValueError as error:
        st.error(str(error))
        return

    try:
        customer = fetch_customer(client, customer_id)
        product = fetch_product(client, product_id)
    except DB_ERRORS:
        st.error("Could not reach Supabase to validate the order. Nothing was saved.")
        return

    if customer is None or product is None:
        st.error(
            "The selected customer or product no longer exists. Select Refresh "
            "Data and choose again. Nothing was saved."
        )
        return

    current_price = Decimal(str(product["price"]))
    if current_price != reviewed_price:
        # Update the cached product so the review shows the new price; the
        # confirmation checkbox key includes the price, so it resets to unchecked.
        st.session_state["products"] = [
            product if int(row["product_id"]) == product_id else row
            for row in st.session_state["products"]
        ]
        st.session_state["notice"] = (
            "warning",
            f"The price of {product['product_name']} changed from "
            f"{_money(reviewed_price)} to {_money(current_price)}. "
            "Review the updated total and confirm again. Nothing was saved.",
        )
        st.rerun()

    try:
        order_id = create_order(client, customer_id, product_id, quantity, product["price"])
    except DB_ERRORS:
        st.error(
            "Supabase did not confirm the order. Check the connection and "
            "permissions before trying again. Nothing was confirmed as saved."
        )
        return

    # Insertion succeeded: reset the form so the same order is not resubmitted,
    # and refresh order history on the next run.
    st.session_state["form_nonce"] = st.session_state.get("form_nonce", 0) + 1
    st.session_state.pop("order_history", None)
    st.session_state["last_order_id"] = order_id
    st.session_state["verified_order"] = None
    _verify_last_order(client)
    st.rerun()


def _verify_last_order(client: Client) -> None:
    """Retrieve the just-saved order from Supabase with a new query."""
    order_id = st.session_state.get("last_order_id")
    if order_id is None:
        return
    try:
        order = retrieve_saved_order(client, order_id)
    except DB_ERRORS:
        order = None
    st.session_state["verified_order"] = order


def _render_order_form(client: Client, customers: list[dict], products: list[dict]) -> None:
    st.header("Enter an order")
    if not customers or not products:
        st.error("Cannot create an order: customers or products are missing.")
        return

    customer_by_id = {int(row["customer_id"]): row for row in customers}
    product_by_id = {int(row["product_id"]): row for row in products}

    customer_id = st.selectbox(
        "1. Customer",
        options=list(customer_by_id),
        key="order_customer",
        index=None,
        placeholder="Select a customer",
        format_func=lambda cid: f"{customer_by_id[cid]['name']} (ID {cid})",
    )
    product_id = st.selectbox(
        "2. Product",
        options=list(product_by_id),
        key="order_product",
        index=None,
        placeholder="Select a product",
        format_func=lambda pid: (
            f"{product_by_id[pid]['product_name']} — {_money(product_by_id[pid]['price'])}"
        ),
    )
    quantity = st.number_input(
        "3. Quantity", min_value=1, step=1, value=1, format="%d", key="order_quantity"
    )

    if customer_id is None or product_id is None:
        st.info("Select a customer and a product to review the order.")
        return

    customer = customer_by_id[customer_id]
    product = product_by_id[product_id]
    unit_price = Decimal(str(product["price"]))

    st.subheader("4. Review order")
    st.table(
        {
            "Field": ["Customer", "Product", "Quantity", "Unit Price", "Total"],
            "Value": [
                customer["name"],
                product["product_name"],
                str(int(quantity)),
                _money(unit_price),
                _money(unit_price * int(quantity)),
            ],
        }
    )

    # The key changes whenever the reviewed order changes (or after a save),
    # so any change of selection, quantity, or price clears the confirmation.
    confirm_key = (
        f"confirm-{st.session_state.get('form_nonce', 0)}-"
        f"{customer_id}-{product_id}-{int(quantity)}-{unit_price}"
    )
    confirmed = st.checkbox("I have reviewed this order and confirm it.", key=confirm_key)

    if st.button("5. Submit order", type="primary"):
        if not confirmed:
            st.warning("Check the confirmation box before submitting. Nothing was saved.")
            return
        _submit_order(client, customer_id, product_id, int(quantity), unit_price)


# --------------------------------------------------------------------------
# Section 4: verification and order history
# --------------------------------------------------------------------------
def _order_row(order: dict[str, Any]) -> dict[str, Any]:
    unit_price = Decimal(str(order["unit_price"]))
    quantity = int(order["quantity"])
    return {
        "Order ID": order["order_id"],
        "Customer": order["customer_name"],
        "Product": order["product_name"],
        "Quantity": quantity,
        "Unit Price": _money(unit_price),
        "Total": _money(unit_price * quantity),
        "Order Date": str(order["order_date"]),
    }


def _render_verification(client: Client) -> None:
    order_id = st.session_state.get("last_order_id")
    if order_id is None:
        return

    st.header("Saved order verification")
    order = st.session_state.get("verified_order")
    if order is None:
        st.warning(
            f"Order {order_id} was saved, but it could not be retrieved from "
            "Supabase for verification. It will not be submitted again."
        )
        if st.button("Retry verification"):
            _verify_last_order(client)
            st.rerun()
        return

    st.success(f"Order {order_id} was saved and verified in Supabase.")
    st.dataframe([_order_row(order)], hide_index=True, width="stretch")


def _render_order_history(customers: list[dict], products: list[dict]) -> None:
    st.header("Order History")
    history = st.session_state.get("order_history", [])
    customer_names = {int(c["customer_id"]): c["name"] for c in customers}
    product_names = {int(p["product_id"]): p["product_name"] for p in products}

    filter_id = st.selectbox(
        "Filter by customer",
        options=[None, *customer_names],
        format_func=lambda cid: "All customers" if cid is None else customer_names[cid],
    )
    if filter_id is not None:
        history = [o for o in history if int(o["customer_id"]) == filter_id]

    if not history:
        st.info("No orders found.")
        return

    rows = [
        _order_row(
            {
                **order,
                "customer_name": customer_names.get(
                    int(order["customer_id"]), f"Customer {order['customer_id']}"
                ),
                "product_name": product_names.get(
                    int(order["product_id"]), f"Product {order['product_id']}"
                ),
            }
        )
        for order in history
    ]
    st.dataframe(rows, hide_index=True, width="stretch")

    total = sum(
        Decimal(str(o["unit_price"])) * int(o["quantity"]) for o in history
    )
    label = "all customers" if filter_id is None else customer_names[filter_id]
    st.metric(f"Total value of orders for {label}", _money(total))


# --------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Campus Store Orders", layout="wide")
    _require_password()

    st.title("Campus Store Order Entry")
    st.caption(
        "View current customers and products from Supabase, enter an order, "
        "confirm it, and verify the saved record retrieved from the database."
    )

    try:
        client = _create_app_client()
    except SystemExit:
        st.error(
            "Supabase credentials are missing. Add SUPABASE_URL and "
            "SUPABASE_KEY to the app secrets (or a local .env file)."
        )
        st.stop()
    except Exception:  # noqa: BLE001 - never show credential details
        st.error("Could not connect to Supabase. Check the configured URL and key.")
        st.stop()

    if st.button("Refresh Data"):
        _clear_cached_data()
        st.rerun()

    if not _load_data(client):
        return

    notice = st.session_state.pop("notice", None)
    if notice:
        getattr(st, notice[0])(notice[1])

    customers = st.session_state["customers"]
    products = st.session_state["products"]

    _render_catalog(customers, products)
    st.divider()
    _render_order_form(client, customers, products)
    _render_verification(client)
    st.divider()
    _render_order_history(customers, products)


if __name__ == "__main__":
    main()
