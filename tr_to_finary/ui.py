"""Rich-based terminal UI for tr-to-finary."""

import io
import sys

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from .aggregator import Position
from .parser_tr import Transaction
from .sync_state import SyncState

# Force UTF-8 output on Windows to avoid encoding errors with special chars
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(force_terminal=True)


LOGO = r"""
 _____ ___    _          ___ _
|_   _| _ \  | |_ ___   | __(_)_ _  __ _ _ _ _  _
  | | |   /  |  _/ _ \  | _|| | ' \/ _` | '_| || |
  |_| |_|_\   \__\___/  |_| |_|_||_\__,_|_|  \_, |
                                               |__/
"""


def print_banner():
    console.print(Panel(
        Text(LOGO, style="bold cyan", justify="center"),
        subtitle="Trade Republic -> Finary Sync",
        border_style="cyan",
        box=box.DOUBLE,
    ))


def print_step(number: int, text: str):
    console.print(f"\n[bold cyan]{'─' * 50}[/]")
    console.print(f"[bold white] Step {number}:[/] [bold]{text}[/]")
    console.print(f"[bold cyan]{'─' * 50}[/]")


def print_success(text: str):
    console.print(f"  [bold green]✓[/] {text}")


def print_warning(text: str):
    console.print(f"  [bold yellow]![/] {text}")


def print_error(text: str):
    console.print(f"  [bold red]✗[/] {text}")


def print_info(text: str):
    console.print(f"  [dim]->[/] {text}")


def print_transactions_table(transactions: list[Transaction]):
    table = Table(
        title="Transactions",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("Date", style="white", width=12)
    table.add_column("Type", style="bold", width=12)
    table.add_column("ISIN", style="dim", width=14)
    table.add_column("Name", width=30)
    table.add_column("Shares", justify="right", width=12)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Amount", justify="right", width=10)
    table.add_column("Fees", justify="right", width=7)

    for tx in transactions:
        type_style = {
            "BUY": "green",
            "SELL": "red",
            "DIVIDEND": "yellow",
            "INTEREST_PAYMENT": "blue",
        }.get(tx.type, "white")

        table.add_row(
            str(tx.date),
            f"[{type_style}]{tx.type}[/]",
            tx.isin or "",
            tx.name[:30],
            f"{tx.shares:.6f}" if tx.shares else "",
            f"{tx.price:.2f}" if tx.price else "",
            f"{tx.amount:.2f} {tx.currency}",
            f"{tx.fee:.2f}" if tx.fee else "",
        )

    console.print(table)


def print_positions_table(
    positions: list[Position],
    new_tx_ids: set[str] | None = None,
    title: str = "Positions",
):
    table = Table(
        title=title,
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        header_style="bold cyan",
        expand=False,
        pad_edge=True,
    )
    table.add_column("Name", style="white", no_wrap=True)
    table.add_column("ISIN", style="dim")
    table.add_column("Qty", justify="right")
    table.add_column("Avg Price", justify="right")
    table.add_column("Invested", justify="right")
    table.add_column("Status", justify="center")

    total_invested = 0.0

    for pos in positions:
        total_invested += pos.total_invested

        new_count = 0
        if new_tx_ids:
            new_count = sum(1 for tid in pos.transaction_ids if tid in new_tx_ids)

        status = f"[bold green]+{new_count} new[/]" if new_count else "[dim]ok[/]"
        div = f" [yellow]+{pos.total_dividends:.2f} div[/]" if pos.total_dividends else ""

        table.add_row(
            pos.name,
            pos.isin,
            f"{pos.quantity:.4f}",
            f"{pos.average_buy_price:.2f} EUR",
            f"{pos.total_invested:.2f} EUR{div}",
            status,
        )

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/]", "", "", "",
        f"[bold]{total_invested:.2f} EUR[/]",
        f"[bold]{len(positions)} pos[/]",
    )

    console.print(table)


def print_sync_summary(created: int, updated: int, skipped: int, errors: int):
    parts = []
    if created:
        parts.append(f"[bold green]{created} created[/]")
    if updated:
        parts.append(f"[bold cyan]{updated} updated[/]")
    if skipped:
        parts.append(f"[dim]{skipped} skipped[/]")
    if errors:
        parts.append(f"[bold red]{errors} errors[/]")

    console.print(Panel(
        " | ".join(parts) if parts else "[dim]Nothing to do[/]",
        title="Sync Result",
        border_style="green" if not errors else "red",
    ))


def confirm_update(pos: Position, existing: dict) -> str:
    """Show old vs new values and ask for confirmation. Returns 'y', 'n', or 'a'."""
    old_qty = existing.get("quantity", 0)
    old_price = existing.get("display_buying_price", 0)
    qty_changed = abs(pos.quantity - old_qty) > 0.0001
    price_changed = abs(pos.average_buy_price - old_price) > 0.01

    if not qty_changed and not price_changed:
        return "skip"

    console.print(f"\n  [bold yellow]UPDATE[/] {pos.name} ([dim]{pos.isin}[/]):")
    if qty_changed:
        console.print(f"    quantity:  [red]{old_qty:>12.6f}[/]  ->  [green]{pos.quantity:>12.6f}[/]")
    if price_changed:
        console.print(f"    avg price: [red]{old_price:>12.4f}[/]  ->  [green]{pos.average_buy_price:>12.4f}[/]")

    answer = console.input("    [bold]Apply? [y/N/a(ll)][/] ").strip().lower()
    return answer if answer in ("y", "yes", "a", "all") else "n"


def confirm_create(pos: Position) -> str:
    """Show new position and ask for confirmation. Returns 'y', 'n', or 'a'."""
    console.print(f"\n  [bold green]CREATE[/] {pos.name} ([dim]{pos.isin}[/]):")
    console.print(f"    quantity:  [green]{pos.quantity:>12.6f}[/]")
    console.print(f"    avg price: [green]{pos.average_buy_price:>12.4f} {pos.currency}[/]")
    console.print(f"    invested:  [green]{pos.total_invested:>12.2f} {pos.currency}[/]")

    answer = console.input("    [bold]Create? [y/N/a(ll)][/] ").strip().lower()
    return answer if answer in ("y", "yes", "a", "all") else "n"
