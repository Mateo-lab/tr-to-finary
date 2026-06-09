"""CLI entry point for tr-to-finary."""

import argparse
import sys
from pathlib import Path

from .parser_tr import parse_tr_csv, filter_trading, filter_dividends
from .aggregator import aggregate_positions
from .finary_sync import sync_positions_to_finary
from .sync_state import load_state, save_state, SyncState
from .ui import (
    console, print_banner, print_step, print_success, print_error,
    print_warning, print_info, print_transactions_table, print_positions_table,
)


def main():
    parser = argparse.ArgumentParser(
        description="Sync Trade Republic transactions to Finary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tr-to-finary --setup                        First-time setup wizard
  tr-to-finary --fetch                         Fetch from TR + dry run
  tr-to-finary --fetch --execute               Fetch + sync to Finary
  tr-to-finary --fetch --execute --yes         Fetch + sync (auto-approve)
  tr-to-finary export.csv                      From CSV + dry run
  tr-to-finary export.csv --execute            From CSV + sync
  tr-to-finary export.csv --parse-only         Just show transactions
  tr-to-finary export.csv --reset --execute    Force full re-sync
        """,
    )
    parser.add_argument(
        "csv_file", type=Path, nargs="?", default=None,
        help="Path to Trade Republic CSV export (not needed with --fetch)",
    )
    parser.add_argument("--setup", action="store_true", help="Run the interactive setup wizard")
    parser.add_argument("--fetch", action="store_true", help="Fetch transactions from TR via pytr")
    parser.add_argument("--last-days", type=int, default=0, help="With --fetch: only last N days (0 = all)")
    parser.add_argument("--execute", action="store_true", help="Actually sync to Finary (default: dry run)")
    parser.add_argument("--account", default="Trade Republic", help="Finary account name")
    parser.add_argument("--parse-only", action="store_true", help="Only show transactions")
    parser.add_argument("--trades-only", action="store_true", help="Filter to BUY/SELL only")
    parser.add_argument("--reset", action="store_true", help="Reset sync state")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve all changes")

    args = parser.parse_args()

    # Setup wizard
    if args.setup:
        from .setup_wizard import run_setup
        run_setup()
        return

    print_banner()

    if not args.fetch and args.csv_file is None:
        console.print("[bold red]Error:[/] Provide a CSV file or use [cyan]--fetch[/]\n")
        console.print("  [dim]First time? Run:[/] [bold cyan]python -m tr_to_finary.cli --setup[/]\n")
        console.print("  [dim]Quick start:[/]")
        console.print("    [cyan]python -m tr_to_finary.cli --fetch[/]           Fetch from TR + preview")
        console.print("    [cyan]python -m tr_to_finary.cli export.csv[/]        From manual CSV export")
        sys.exit(1)

    # Step 1: Get CSV
    print_step(1, "Fetching data" if args.fetch else "Reading CSV")

    if args.fetch:
        from .tr_export import fetch_transactions
        output_dir = Path(".")
        try:
            csv_path = fetch_transactions(output_dir=output_dir, last_days=args.last_days)
            print_success(f"Exported to {csv_path}")
        except RuntimeError as e:
            print_error(str(e))
            if "not installed" in str(e).lower():
                console.print("\n  [dim]Install pytr:[/] [bold cyan]pip install pytr[/]")
                console.print("  [dim]Then login:[/]  [bold cyan]python -m pytr login --store_credentials[/]")
            sys.exit(1)
    else:
        csv_path = args.csv_file
        if not csv_path.exists():
            print_error(f"File not found: {csv_path}")
            sys.exit(1)

    # Step 2: Parse
    print_step(2, "Parsing transactions")

    transactions = parse_tr_csv(csv_path)
    print_success(f"Found {len(transactions)} transactions")

    if args.parse_only:
        display = transactions
        if args.trades_only:
            display = filter_trading(transactions)
            print_info(f"Filtered to {len(display)} trading transactions")
        print_transactions_table(display)
        return

    # Step 3: Aggregate
    print_step(3, "Aggregating positions")

    state_dir = csv_path.parent
    state = SyncState() if args.reset else load_state(state_dir)

    if args.reset:
        print_warning("Sync state reset — all transactions treated as new")

    trading = filter_trading(transactions)
    dividends = filter_dividends(transactions)
    all_relevant = trading + dividends

    print_info(f"{len(trading)} trades, {len(dividends)} dividends, "
               f"{len(state.synced_transaction_ids)} previously synced")

    positions = aggregate_positions(all_relevant)
    print_success(f"Aggregated into {len(positions)} open positions")

    # Step 4: Sync
    print_step(4, "Syncing to Finary" if args.execute else "Preview (dry run)")

    sync_positions_to_finary(
        positions,
        state=state,
        account_name=args.account,
        dry_run=not args.execute,
        auto_confirm=args.yes,
    )

    if args.execute:
        save_state(state, state_dir)
        print_info(f"Sync state saved to {state_dir / '.sync_state.json'}")


if __name__ == "__main__":
    main()
