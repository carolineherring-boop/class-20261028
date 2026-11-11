# Campus Store Order Entry (DATA 4000 — Streamlit + Supabase)

A Streamlit web app that loads customers and products from Supabase, lets a user
enter a single-product order, requires explicit confirmation, saves the order,
and then **re-queries Supabase** to verify the saved record.

**Deployed app:** <https://YOUR-APP-NAME.streamlit.app> ← _replace after deploying_
**Repository:** <https://github.com/carolineherring-boop/class-20261028>

Access is restricted by a server-checked password (`APP_PASSWORD` in the
deployment secrets). The password is provided to the instructor privately
through the course submission system.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit interface (entry point) |
| `order_entry.py` | Supabase client + database functions (fetch, insert, history) |
| `retrieve_saved_order.py` | New API query that retrieves a saved order for verification |
| `order_validation.py` | Quantity / ID validation (reused from the terminal version) |
| `collect_order_input.py`, `print_table.py` | Earlier terminal versions of the program |
| `requirements.txt` | Packages required to run the app |
| `.gitignore` | Excludes `.env`, `.streamlit/secrets.toml`, venvs, caches |
| `.env.example`, `.streamlit/secrets.toml.example` | Example configuration — placeholder values only |

## How the app works

1. **Access gate** – `_require_password()` runs before any Supabase client is
   created. The password is compared with `hmac.compare_digest`.
2. **Display data** – customers (`customer_id`, `name`) and products
   (`product_id`, `product_name`, `category`, `price`) are fetched from Supabase
   via the API and shown with `st.dataframe`; prices are formatted as currency.
   **Refresh Data** clears the cached data and re-queries Supabase.
3. **Order entry** – customer and product dropdowns show names (the IDs are kept
   as the option values), a whole-number `number_input` (min 1) holds the
   quantity, and a review table shows customer, product, quantity, unit price,
   and total.
4. **Confirmation** – the confirmation checkbox's key includes the customer,
   product, quantity, price, and a form counter, so changing anything (or saving
   successfully) un-confirms it. Clicking **Submit** without confirming saves
   nothing.
5. **Validation & save** – on submit the app re-validates the quantity,
   re-fetches the customer and product from Supabase, and compares the current
   price with the reviewed price. If the price changed, it shows the new price
   and requires confirmation again. Otherwise it inserts one row with today's
   date; the database generates `order_id`. Insertion happens only inside the
   Submit button branch, so ordinary reruns, refreshes, or widget changes never
   insert again.
6. **Verification** – using the returned `order_id`, the app makes a new
   query (`retrieve_saved_order`) and shows Order ID, Customer, Product,
   Quantity, Unit Price, Total (from the stored `unit_price`), and Order Date.
   If saving succeeded but verification fails, it says so, offers
   **Retry verification**, and never resubmits.
7. **Order History** – retrieved from Supabase; refreshed after a successful
   insert and on **Refresh Data**.
8. **Extra credit** – a customer filter on Order History shows only that
   customer's orders and the total value of those orders using their stored
   sale prices.

Errors from Supabase (`postgrest.APIError`, `httpx.HTTPError`) are caught and
shown as helpful messages without credentials; no success message is shown
unless the insert succeeded.

### Libraries / techniques beyond class material

- `st.session_state` – caches data and tracks the last saved order between reruns.
- Dynamic widget keys – reset the confirmation checkbox when the order changes.
- `hmac.compare_digest` – constant-time password comparison for the access gate.
- `st.secrets` – reads credentials from Streamlit Community Cloud secrets.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env   # then fill in real values (never commit .env)
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. Open <https://share.streamlit.io/>, choose **Create app**, select
   `carolineherring-boop/class-20261028`, branch `main`, main file `app.py`.
3. Under **Advanced settings → Secrets**, paste (with real values):

   ```toml
   SUPABASE_URL = "https://your-project-id.supabase.co"
   SUPABASE_KEY = "your-rotated-secret-key"
   APP_PASSWORD = "your-class-password"
   ```

4. Deploy, then put the app URL at the top of this README.

Never commit `.env`, `.streamlit/secrets.toml`, or real API keys.

## Testing results (deployed application)

_Fill in after testing the deployed URL._

| Test | Expected result | Result |
|------|-----------------|--------|
| Open the deployed app | Interface loads after authorized access | ☐ |
| View customers and products | Records are retrieved from Supabase | ☐ |
| Try an invalid quantity | Input is prevented or rejected (min 1, whole numbers only) | ☐ |
| Submit without confirmation | No order is inserted (warning shown) | ☐ |
| Confirm and submit a valid order | Exactly one order is inserted | ☐ |
| View the verification table | Newly saved order is retrieved from Supabase | ☐ |
| Refresh or interact with another widget | Previously submitted order is not inserted again | ☐ |
| Refresh order history | Saved order remains visible | ☐ |

## Screenshots

Credentials are never shown in the app, so screenshots will not reveal them.

![Order entry interface](docs/screenshots/order-entry.png)
![Verified order](docs/screenshots/verified-order.png)
