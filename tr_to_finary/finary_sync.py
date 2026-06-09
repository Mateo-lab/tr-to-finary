"""Sync aggregated positions to Finary using finary_uapi."""

import logging

from .aggregator import Position
from .sync_state import SyncState
from .ui import (
    console, print_success, print_error, print_warning, print_info,
    print_positions_table, print_sync_summary,
    confirm_update, confirm_create,
)


def _find_new_transaction_ids(positions: list[Position], state: SyncState) -> set[str]:
    all_ids = set()
    for pos in positions:
        all_ids.update(pos.transaction_ids)
    return all_ids - state.synced_transaction_ids


def _positions_with_changes(positions: list[Position], new_tx_ids: set[str]) -> list[Position]:
    return [
        pos for pos in positions
        if any(tid in new_tx_ids for tid in pos.transaction_ids)
    ]


def _finary_signin():
    """Sign in to Finary, handling 2FA if needed. Returns session or None."""
    from finary_uapi.signin import signin
    from finary_uapi.auth import prepare_session

    try:
        result = signin()
    except RuntimeError as e:
        if "OTP" in str(e):
            otp = console.input("  [bold]Enter your Finary 2FA code:[/] ").strip()
            try:
                result = signin(otp_code=otp)
            except RuntimeError as e2:
                print_error(f"2FA failed — {e2}")
                return None
        else:
            print_error(f"Sign in failed — {e}")
            return None

    status = result.get("response", {}).get("status", "")
    if status != "complete":
        errors = result.get("errors", [])
        if errors:
            msgs = ", ".join(e.get("long_message", str(e)) for e in errors)
            print_error(f"Sign in failed — {msgs}")
        else:
            print_error(f"Sign in failed — status: {status}")
        return None

    return prepare_session()


def sync_positions_to_finary(
    positions: list[Position],
    state: SyncState,
    account_name: str = "Trade Republic",
    dry_run: bool = True,
    auto_confirm: bool = False,
):
    new_tx_ids = _find_new_transaction_ids(positions, state)
    changed_positions = _positions_with_changes(positions, new_tx_ids)

    if not new_tx_ids:
        console.print("\n[bold green]All transactions already synced![/]\n")
        print_positions_table(positions, title="Current Positions")
        print_info("Export a fresh CSV or use --fetch to pick up new trades.")
        return

    console.print(f"\n  [bold]{len(new_tx_ids)}[/] new transactions → "
                  f"[bold]{len(changed_positions)}[/] positions to create/update\n")

    if dry_run:
        console.print("[bold yellow]DRY RUN — no changes will be made[/]\n")
        print_positions_table(positions, new_tx_ids, title="Positions (Dry Run)")
        console.print("\n  Re-run with [bold cyan]--execute[/] to apply changes to Finary.")
        return

    try:
        from finary_uapi.user_securities import (
            add_user_security,
            update_user_security,
        )
        from finary_uapi.user_holdings_accounts import (
            get_holdings_account_per_name_or_id,
            add_holdings_account,
        )
        from finary_uapi.securities import guess_security
    except ImportError:
        print_error("finary-uapi is not installed.")
        console.print("  Run: [bold cyan]pip install finary-uapi[/]")
        console.print("  Then: [bold cyan]python -m tr_to_finary.cli --setup[/]")
        return

    session = _finary_signin()
    if session is None:
        return

    print_success(f"Signed in to Finary")
    print_info(f"Syncing to account: [bold]{account_name}[/]")

    # Get or create the holdings account
    account = get_holdings_account_per_name_or_id(session, account_name)
    if not account:
        print_info(f"Creating account '{account_name}'...")
        result = add_holdings_account(session, account_name, "stocks")
        account = result.get("result", result)

    account_id = account["id"]

    # Index existing securities by ISIN
    existing_by_isin: dict[str, dict] = {}
    for sec in account.get("securities", []):
        isin = sec.get("security", {}).get("isin", "")
        if isin:
            existing_by_isin[isin] = sec

    logging.basicConfig(level=logging.INFO, format="  %(message)s")

    created = 0
    updated = 0
    skipped = 0
    errors = 0
    approve_all = auto_confirm

    for pos in positions:
        has_changes = any(tid in new_tx_ids for tid in pos.transaction_ids)
        if not has_changes:
            continue

        if pos.isin in existing_by_isin:
            existing = existing_by_isin[pos.isin]

            if approve_all:
                answer = "y"
            else:
                answer = confirm_update(pos, existing)

            if answer == "skip":
                for tid in pos.transaction_ids:
                    if tid in new_tx_ids:
                        state.mark_synced(tid)
                continue

            if answer in ("a", "all"):
                approve_all = True
                answer = "y"

            if answer not in ("y", "yes"):
                print_warning(f"Skipped {pos.name}")
                skipped += 1
                continue

            try:
                result = update_user_security(
                    session, existing, pos.quantity, pos.average_buy_price, account_id,
                )
                print_success(f"Updated {pos.name}")
                updated += 1
                for tid in pos.transaction_ids:
                    if tid in new_tx_ids:
                        state.mark_synced(tid)
            except Exception as e:
                print_error(f"Failed {pos.name}: {e}")
                errors += 1

        else:
            # New position
            import_line = {
                "isin_code": pos.isin,
                "currency": pos.currency,
                "description": pos.name,
            }
            finary_security = guess_security(session, import_line)
            if not finary_security:
                print_warning(f"Not found in Finary: {pos.name} ({pos.isin})")
                skipped += 1
                continue

            if approve_all:
                answer = "y"
            else:
                answer = confirm_create(pos)

            if answer in ("a", "all"):
                approve_all = True
                answer = "y"

            if answer not in ("y", "yes"):
                print_warning(f"Skipped {pos.name}")
                skipped += 1
                continue

            try:
                result = add_user_security(
                    session, account_id, finary_security["correlation_id"],
                    pos.quantity, pos.average_buy_price,
                )
                print_success(f"Created {pos.name}")
                created += 1
                for tid in pos.transaction_ids:
                    if tid in new_tx_ids:
                        state.mark_synced(tid)
            except Exception as e:
                print_error(f"Failed {pos.name}: {e}")
                errors += 1

    state.finary_account = account_name
    console.print()
    print_sync_summary(created, updated, skipped, errors)
