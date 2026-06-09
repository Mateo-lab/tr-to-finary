"""Parse Trade Republic CSV exports into normalized transactions.

Supports two formats:
- Native TR export (from app: Profile > Account Statements > Transaction Export)
- pytr export (from `pytr export_transactions`)
"""

import csv
from pathlib import Path
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, auto


class CsvFormat(Enum):
    NATIVE_TR = auto()   # Trade Republic app export
    PYTR = auto()        # pytr export_transactions


@dataclass
class Transaction:
    date: date
    category: str       # "CASH" or "TRADING"
    type: str           # "BUY", "SELL", "DIVIDEND", "INTEREST_PAYMENT", etc.
    asset_class: str    # "FUND", "STOCK", ""
    name: str
    isin: str | None
    shares: float | None
    price: float | None
    amount: float
    fee: float
    tax: float
    currency: str
    description: str
    transaction_id: str


def _parse_float(value: str) -> float:
    if not value or value.strip() == "":
        return 0.0
    return float(value.strip())


def _detect_format(fieldnames: list[str]) -> CsvFormat:
    """Auto-detect CSV format based on column headers."""
    lower_fields = {f.lower().strip() for f in fieldnames}

    # Native TR has: datetime, date, account_type, category, type, ...
    if "category" in lower_fields and "account_type" in lower_fields:
        return CsvFormat.NATIVE_TR

    # pytr has: Date, Type, Value, Note, ISIN, Shares, Fees, Taxes
    if "isin" in lower_fields and "shares" in lower_fields and "value" in lower_fields:
        return CsvFormat.PYTR

    # pytr localized (French): Date, Type, Valeur, Note, ISIN, Parts, Frais, Taxes
    if "valeur" in lower_fields or "parts" in lower_fields:
        return CsvFormat.PYTR

    raise ValueError(
        f"Unknown CSV format. Columns found: {fieldnames}\n"
        "Expected either Trade Republic native export or pytr export."
    )


# pytr type mappings (English)
PYTR_TYPE_MAP = {
    "Buy": "BUY",
    "Sell": "SELL",
    "Dividend": "DIVIDEND",
    "Interest": "INTEREST_PAYMENT",
    "Deposit": "CUSTOMER_INBOUND",
    "Removal": "CUSTOMER_OUTBOUND",
    "Taxes": "TAX",
    "Tax Refund": "TAX_REFUND",
    # French
    "Achat": "BUY",
    "Vente": "SELL",
    "Dividende": "DIVIDEND",
    "Intérêts": "INTEREST_PAYMENT",
    "Dépôt": "CUSTOMER_INBOUND",
    "Retrait": "CUSTOMER_OUTBOUND",
    "Impôts": "TAX",
    # German
    "Kauf": "BUY",
    "Verkauf": "SELL",
    "Dividende": "DIVIDEND",
    "Zinsen": "INTEREST_PAYMENT",
    "Einzahlung": "CUSTOMER_INBOUND",
    "Auszahlung": "CUSTOMER_OUTBOUND",
    "Steuern": "TAX",
}


def _find_col(row: dict, candidates: list[str]) -> str:
    """Find the first matching column (case-insensitive)."""
    lower_row = {k.lower().strip(): k for k in row.keys()}
    for c in candidates:
        if c.lower() in lower_row:
            return lower_row[c.lower()]
    return ""


def _parse_pytr_row(row: dict, row_index: int) -> Transaction:
    """Parse a row from pytr CSV format."""
    col_date = _find_col(row, ["Date", "Datum"])
    col_type = _find_col(row, ["Type", "Typ"])
    col_value = _find_col(row, ["Value", "Valeur", "Wert"])
    col_note = _find_col(row, ["Note", "Notiz"])
    col_isin = _find_col(row, ["ISIN"])
    col_shares = _find_col(row, ["Shares", "Parts", "Anteile"])
    col_fees = _find_col(row, ["Fees", "Frais", "Gebühren"])
    col_taxes = _find_col(row, ["Taxes", "Impôts", "Steuern"])

    date_str = row.get(col_date, "").strip()
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%d.%m.%Y"]:
        try:
            tx_date = datetime.strptime(date_str, fmt).date()
            break
        except (ValueError, TypeError):
            continue
    else:
        tx_date = datetime.fromisoformat(date_str).date()

    raw_type = row.get(col_type, "").strip()
    tx_type = PYTR_TYPE_MAP.get(raw_type, raw_type.upper())

    value = _parse_float(row.get(col_value, ""))
    isin = row.get(col_isin, "").strip() or None
    shares = _parse_float(row.get(col_shares, "")) or None
    fees = _parse_float(row.get(col_fees, ""))
    taxes = _parse_float(row.get(col_taxes, ""))
    note = row.get(col_note, "").strip()

    # Determine category and price
    if tx_type in ("BUY", "SELL"):
        category = "TRADING"
        price = abs(value / shares) if shares and shares != 0 else None
    elif tx_type == "DIVIDEND":
        category = "CASH"
        price = None
    else:
        category = "CASH"
        price = None

    return Transaction(
        date=tx_date,
        category=category,
        type=tx_type,
        asset_class="",  # pytr doesn't export asset class
        name=note,
        isin=isin,
        shares=shares,
        price=price,
        amount=value,
        fee=fees,
        tax=taxes,
        currency="EUR",
        description=note,
        transaction_id=f"pytr-{row_index}-{date_str}-{isin or 'cash'}-{value}",
    )


def _parse_native_row(row: dict) -> Transaction:
    """Parse a row from native TR CSV format."""
    tx_date = datetime.strptime(row["date"], "%Y-%m-%d").date()

    return Transaction(
        date=tx_date,
        category=row.get("category", "").strip(),
        type=row.get("type", "").strip(),
        asset_class=row.get("asset_class", "").strip(),
        name=row.get("name", "").strip(),
        isin=row.get("symbol", "").strip() or None,
        shares=_parse_float(row.get("shares", "")) or None,
        price=_parse_float(row.get("price", "")) or None,
        amount=_parse_float(row.get("amount", "")),
        fee=_parse_float(row.get("fee", "")),
        tax=_parse_float(row.get("tax", "")),
        currency=row.get("currency", "EUR").strip() or "EUR",
        description=row.get("description", "").strip(),
        transaction_id=row.get("transaction_id", "").strip(),
    )


def parse_tr_csv(filepath: str | Path) -> list[Transaction]:
    """Parse a Trade Republic CSV export (native or pytr format)."""
    filepath = Path(filepath)

    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            for sep in [",", ";", "\t"]:
                try:
                    with open(filepath, encoding=encoding, newline="") as f:
                        reader = csv.DictReader(f, delimiter=sep)
                        if not reader.fieldnames or len(reader.fieldnames) < 3:
                            continue

                        fmt = _detect_format(list(reader.fieldnames))
                        transactions = []

                        for i, row in enumerate(reader):
                            if fmt == CsvFormat.NATIVE_TR:
                                transactions.append(_parse_native_row(row))
                            else:
                                transactions.append(_parse_pytr_row(row, i))

                        if transactions:
                            print(f"  Detected format: {fmt.name}")
                            return transactions
                except (ValueError, KeyError):
                    continue
        except UnicodeDecodeError:
            continue

    raise ValueError(
        f"Could not parse {filepath}. "
        "Expected Trade Republic native CSV or pytr export CSV."
    )


def filter_trading(transactions: list[Transaction]) -> list[Transaction]:
    """Keep only TRADING transactions (BUY, SELL)."""
    return [tx for tx in transactions if tx.type in ("BUY", "SELL")]


def filter_dividends(transactions: list[Transaction]) -> list[Transaction]:
    """Keep only DIVIDEND transactions."""
    return [tx for tx in transactions if tx.type == "DIVIDEND"]


def filter_interest(transactions: list[Transaction]) -> list[Transaction]:
    """Keep only INTEREST_PAYMENT transactions."""
    return [tx for tx in transactions if tx.type == "INTEREST_PAYMENT"]
