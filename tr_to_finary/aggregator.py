"""Aggregate individual transactions into positions (per ISIN)."""

from dataclasses import dataclass, field
from .parser_tr import Transaction


@dataclass
class Position:
    isin: str
    name: str
    asset_class: str
    quantity: float
    average_buy_price: float
    currency: str
    total_fees: float
    total_taxes: float
    total_invested: float
    total_dividends: float
    tx_count: int
    transaction_ids: list[str] = field(default_factory=list)


def aggregate_positions(transactions: list[Transaction]) -> list[Position]:
    """
    Aggregate BUY/SELL/DIVIDEND transactions into net positions per ISIN.

    Uses weighted average cost for buy price calculation.
    """
    positions: dict[str, dict] = {}

    for tx in sorted(transactions, key=lambda t: t.date):
        if not tx.isin:
            continue

        if tx.isin not in positions:
            positions[tx.isin] = {
                "name": tx.name,
                "asset_class": tx.asset_class,
                "quantity": 0.0,
                "total_cost": 0.0,
                "currency": tx.currency,
                "total_fees": 0.0,
                "total_taxes": 0.0,
                "total_dividends": 0.0,
                "tx_count": 0,
                "transaction_ids": [],
            }

        pos = positions[tx.isin]
        pos["transaction_ids"].append(tx.transaction_id)

        if tx.type == "BUY":
            qty = tx.shares or 0
            price = tx.price or (abs(tx.amount) / qty if qty else 0)
            pos["total_cost"] += qty * price
            pos["quantity"] += qty
            pos["total_fees"] += abs(tx.fee)
            pos["total_taxes"] += abs(tx.tax)
            pos["tx_count"] += 1

        elif tx.type == "SELL":
            qty = tx.shares or 0
            if pos["quantity"] > 0:
                avg = pos["total_cost"] / pos["quantity"]
                pos["total_cost"] -= qty * avg
            pos["quantity"] -= qty
            pos["total_fees"] += abs(tx.fee)
            pos["total_taxes"] += abs(tx.tax)
            pos["tx_count"] += 1

        elif tx.type == "DIVIDEND":
            pos["total_dividends"] += tx.amount
            pos["total_taxes"] += abs(tx.tax)

        if tx.name:
            pos["name"] = tx.name

    result = []
    for isin, data in positions.items():
        qty = data["quantity"]
        if qty <= 0.0001:
            continue
        result.append(Position(
            isin=isin,
            name=data["name"],
            asset_class=data["asset_class"],
            quantity=round(qty, 6),
            average_buy_price=round(data["total_cost"] / qty, 4) if qty > 0 else 0,
            currency=data["currency"],
            total_fees=round(data["total_fees"], 2),
            total_taxes=round(data["total_taxes"], 2),
            total_invested=round(data["total_cost"], 2),
            total_dividends=round(data["total_dividends"], 2),
            tx_count=data["tx_count"],
            transaction_ids=data["transaction_ids"],
        ))

    return sorted(result, key=lambda p: p.name)
