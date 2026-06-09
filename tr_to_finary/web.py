"""Web UI for TR to Finary sync."""

import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .parser_tr import parse_tr_csv, filter_trading, filter_dividends, Transaction
from .aggregator import aggregate_positions, Position
from .sync_state import load_state, save_state, SyncState

# ── App ──
app = FastAPI(title="TR to Finary")

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ── Session state (single-user tool) ──
_session: dict = {
    "transactions": [],
    "positions": [],
    "new_tx_ids": set(),
    "csv_path": None,
    "account_name": "Trade Republic",
}


def _state_dir() -> Path:
    return Path(".")


def _pos_dict(pos: Position, new_tx_ids: set[str] | None = None) -> dict:
    d = asdict(pos)
    d["new_tx_count"] = sum(1 for tid in pos.transaction_ids if tid in (new_tx_ids or set()))
    return d


def _tx_dict(tx: Transaction) -> dict:
    return {
        "date": str(tx.date),
        "type": tx.type,
        "name": tx.name,
        "isin": tx.isin,
        "shares": tx.shares,
        "price": tx.price,
        "amount": tx.amount,
        "fee": tx.fee,
        "tax": tx.tax,
        "currency": tx.currency,
    }


# ── Pages ──
@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    state = load_state(_state_dir())
    positions = _session.get("positions", [])
    total_invested = sum(p.total_invested for p in positions)
    total_dividends = sum(p.total_dividends for p in positions)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "page": "dashboard",
        "positions": positions,
        "total_invested": total_invested,
        "total_dividends": total_dividends,
    })


@app.get("/sync", response_class=HTMLResponse)
async def page_sync(request: Request):
    return templates.TemplateResponse("sync.html", {
        "request": request,
        "page": "sync",
    })


@app.get("/transactions", response_class=HTMLResponse)
async def page_transactions(request: Request, filter: str = "all"):
    transactions = _session.get("transactions", [])

    counts = {
        "all": len(transactions),
        "trading": len(filter_trading(transactions)),
        "dividends": len(filter_dividends(transactions)),
    }

    if filter == "trading":
        display = filter_trading(transactions)
    elif filter == "dividends":
        display = filter_dividends(transactions)
    else:
        display = transactions

    return templates.TemplateResponse("transactions.html", {
        "request": request,
        "page": "transactions",
        "transactions": display,
        "filter": filter,
        "counts": counts,
    })


@app.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "page": "settings",
    })


# ── API: Status ──
@app.get("/api/status")
async def api_status():
    state = load_state(_state_dir())
    return {
        "synced_count": len(state.synced_transaction_ids),
        "last_sync": state.last_sync,
        "account": state.finary_account,
    }


# ── API: Upload CSV ──
@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file")

    tmp = Path(tempfile.mkdtemp()) / file.filename
    with open(tmp, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        return _process_csv(tmp)
    except Exception as e:
        raise HTTPException(400, str(e))


# ── API: Fetch from TR ──
@app.post("/api/fetch")
async def api_fetch(body: dict = {}):
    try:
        from .tr_export import fetch_transactions
    except ImportError:
        raise HTTPException(400, "pytr is not installed. Run: pip install pytr")

    last_days = body.get("last_days", 0)

    try:
        csv_path = fetch_transactions(output_dir=Path("."), last_days=last_days)
    except RuntimeError as e:
        raise HTTPException(400, str(e))

    try:
        return _process_csv(csv_path)
    except Exception as e:
        raise HTTPException(400, str(e))


def _process_csv(csv_path: Path) -> dict:
    """Parse CSV, aggregate, compute diff."""
    transactions = parse_tr_csv(csv_path)
    state = load_state(_state_dir())

    trading = filter_trading(transactions)
    dividends = filter_dividends(transactions)
    all_relevant = trading + dividends

    positions = aggregate_positions(all_relevant)

    all_tx_ids = set()
    for pos in positions:
        all_tx_ids.update(pos.transaction_ids)
    new_tx_ids = all_tx_ids - state.synced_transaction_ids

    changed = [p for p in positions if any(tid in new_tx_ids for tid in p.transaction_ids)]

    # Store in session
    _session["transactions"] = transactions
    _session["positions"] = positions
    _session["new_tx_ids"] = new_tx_ids
    _session["csv_path"] = csv_path

    return {
        "total_transactions": len(transactions),
        "trading_count": len(trading),
        "dividend_count": len(dividends),
        "positions": [_pos_dict(p, new_tx_ids) for p in positions],
        "transactions": [_tx_dict(tx) for tx in all_relevant],
        "new_tx_count": len(new_tx_ids),
        "changed_count": len(changed),
        "already_synced": len(state.synced_transaction_ids),
    }


# ── API: Sync to Finary ──
@app.post("/api/sync")
async def api_sync(body: dict = {}):
    positions = _session.get("positions", [])
    new_tx_ids = _session.get("new_tx_ids", set())

    if not positions:
        raise HTTPException(400, "No data loaded. Upload a CSV or fetch from TR first.")

    if not new_tx_ids:
        return {"created": 0, "updated": 0, "skipped": 0, "errors": 0,
                "logs": ["All transactions already synced."]}

    account_name = body.get("account_name", _session.get("account_name", "Trade Republic"))
    _session["account_name"] = account_name

    try:
        from finary_uapi.signin import signin
        from finary_uapi.auth import prepare_session
        from finary_uapi.user_securities import add_user_security, update_user_security
        from finary_uapi.user_holdings_accounts import (
            get_holdings_account_per_name_or_id, add_holdings_account,
        )
        from finary_uapi.securities import guess_security
    except ImportError:
        raise HTTPException(400, "finary-uapi is not installed. Run: pip install finary-uapi")

    logs: list[str] = []

    # Sign in
    try:
        result = signin()
    except RuntimeError as e:
        if "OTP" in str(e):
            raise HTTPException(400,
                "Finary requires 2FA. Sign in via CLI first: python -m tr_to_finary.cli --setup")
        raise HTTPException(400, f"Sign in failed: {e}")

    status = result.get("response", {}).get("status", "")
    if status != "complete":
        raise HTTPException(400, f"Sign in failed (status: {status})")

    session = prepare_session()
    logs.append("[OK] Signed in to Finary")

    # Get or create account
    account = get_holdings_account_per_name_or_id(session, account_name)
    if not account:
        logs.append(f"[INFO] Creating account '{account_name}'...")
        result = add_holdings_account(session, account_name, "stocks")
        account = result.get("result", result)

    account_id = account["id"]
    logs.append(f"[OK] Account: {account_name}")

    # Index existing
    existing_by_isin: dict[str, dict] = {}
    for sec in account.get("securities", []):
        isin = sec.get("security", {}).get("isin", "")
        if isin:
            existing_by_isin[isin] = sec

    state = load_state(_state_dir())
    created = updated = skipped = errors = 0

    for pos in positions:
        if not any(tid in new_tx_ids for tid in pos.transaction_ids):
            continue

        if pos.isin in existing_by_isin:
            existing = existing_by_isin[pos.isin]
            old_qty = existing.get("quantity", 0)
            old_price = existing.get("display_buying_price", 0)

            if abs(pos.quantity - old_qty) <= 0.0001 and abs(pos.average_buy_price - old_price) <= 0.01:
                for tid in pos.transaction_ids:
                    if tid in new_tx_ids:
                        state.mark_synced(tid)
                logs.append(f"[INFO] {pos.name}: no changes, marking synced")
                continue

            try:
                update_user_security(session, existing, pos.quantity, pos.average_buy_price, account_id)
                logs.append(f"[OK] Updated {pos.name} (qty: {old_qty:.4f} -> {pos.quantity:.4f})")
                updated += 1
                for tid in pos.transaction_ids:
                    if tid in new_tx_ids:
                        state.mark_synced(tid)
            except Exception as e:
                logs.append(f"[ERR] Failed to update {pos.name}: {e}")
                errors += 1
        else:
            finary_security = guess_security(session, {
                "isin_code": pos.isin, "currency": pos.currency, "description": pos.name,
            })
            if not finary_security:
                logs.append(f"[WARN] {pos.name} ({pos.isin}) not found in Finary")
                skipped += 1
                continue

            try:
                add_user_security(session, account_id, finary_security["correlation_id"],
                                  pos.quantity, pos.average_buy_price)
                logs.append(f"[OK] Created {pos.name} (qty: {pos.quantity:.4f}, price: {pos.average_buy_price:.2f})")
                created += 1
                for tid in pos.transaction_ids:
                    if tid in new_tx_ids:
                        state.mark_synced(tid)
            except Exception as e:
                logs.append(f"[ERR] Failed to create {pos.name}: {e}")
                errors += 1

    state.finary_account = account_name
    save_state(state, _state_dir())
    logs.append(f"[OK] State saved ({len(state.synced_transaction_ids)} txs tracked)")

    _session["new_tx_ids"] = set()

    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors, "logs": logs}


# ── API: Settings ──
@app.get("/api/settings")
async def api_get_settings():
    creds_path = Path("credentials.json")
    email = ""
    if creds_path.exists():
        try:
            email = json.loads(creds_path.read_text(encoding="utf-8")).get("email", "")
        except Exception:
            pass

    state = load_state(_state_dir())
    return {
        "account_name": state.finary_account or _session.get("account_name", "Trade Republic"),
        "has_credentials": creds_path.exists(),
        "email": email,
    }


@app.post("/api/settings")
async def api_save_settings(body: dict):
    _session["account_name"] = body.get("account_name", "Trade Republic")
    return {"ok": True}


# ── API: Reset ──
@app.post("/api/reset")
async def api_reset():
    save_state(SyncState(), _state_dir())
    _session.update({"new_tx_ids": set(), "positions": [], "transactions": []})
    return {"ok": True}


# ── Entry point ──
def main():
    import argparse
    import webbrowser

    parser = argparse.ArgumentParser(description="TR to Finary Web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"\n  TR to Finary Web UI")
    print(f"  {url}\n")

    if not args.no_browser:
        import threading
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run("tr_to_finary.web:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
