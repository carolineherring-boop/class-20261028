# Campus Store Order Entry

Streamlit order-entry app backed by Supabase. It loads current customers and
products, confirms the order total before saving, and retrieves the inserted
order again to verify it.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `SUPABASE_URL` and `SUPABASE_KEY` in `.env`, then run:

```bash
streamlit run streamlit_app.py
```

Never commit `.env` or paste a Supabase key into source code. The key previously
shared for this class project should be rotated before deployment.

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) with the
   GitHub account that can access the repository.
3. Create an app, choose `carolineherring-boop/class-20261028`, branch `main`,
   and main file `streamlit_app.py`.
4. In the app's settings, add these values under **Secrets** using TOML syntax:

   ```toml
   SUPABASE_URL = "https://your-project-id.supabase.co"
   SUPABASE_KEY = "your-rotated-server-side-key"
   ```

5. Save and wait for Streamlit to build the app. Copy the public app URL for
   submission.

The app reads Streamlit Cloud Secrets first and falls back to `.env` for local
development. Keep the Supabase key in Secrets; do not commit it to GitHub.

This assignment app currently has no user sign-in. Anyone who can reach its
public URL can submit an order, so only deploy it publicly if that behavior is
acceptable for your class project. The server-side key is not sent to the
browser, but it should be a dedicated, rotated key and remain private.
