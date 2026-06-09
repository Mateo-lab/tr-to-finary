# TR to Finary

Sync your **Trade Republic** portfolio to **[Finary](https://finary.com)** automatically.

> Finary's Trade Republic provider is broken? No worries. This tool reads your TR transactions and syncs your positions to Finary via its API.

## Features

- **Two data sources**: manual CSV export from TR app, or automatic fetch via [pytr](https://github.com/pytr-org/pytr)
- **Smart sync**: only new transactions are processed (tracked via `.sync_state.json`)
- **Interactive confirmation**: review each create/update before it's applied
- **Position aggregation**: computes weighted average buy price from all your trades
- **Dividend tracking**: dividends are tracked per position
- **Multi-format**: auto-detects Trade Republic native CSV and pytr CSV formats

## Quick Start

### 1. Install

```bash
pip install finary-uapi pytr rich
```

### 2. Setup

```bash
python -m tr_to_finary.cli --setup
```

This interactive wizard will:
- Check dependencies
- Create your Finary credentials file
- Test the Finary connection
- Optionally set up Trade Republic login (pytr)

### 3. Sync

**Automatic (recommended):**
```bash
# Preview what would be synced
python -m tr_to_finary.cli --fetch

# Actually sync
python -m tr_to_finary.cli --fetch --execute
```

**From manual CSV export:**
```bash
# Export CSV from TR app: Profile > Account Statements > Transaction Export
python -m tr_to_finary.cli "Exportation de transactions.csv" --execute
```

## Usage

```
python -m tr_to_finary.cli [OPTIONS] [CSV_FILE]

Options:
  --setup          Interactive setup wizard
  --fetch          Fetch transactions from TR via pytr
  --last-days N    With --fetch: only last N days (0 = all)
  --execute        Actually sync to Finary (default: dry run)
  --account NAME   Finary account name (default: "Trade Republic")
  --parse-only     Only show parsed transactions
  --trades-only    Filter to BUY/SELL only
  --reset          Reset sync state (treat all as new)
  --yes, -y        Auto-approve all changes
```

## Examples

```bash
# First time setup
python -m tr_to_finary.cli --setup

# Fetch from TR + preview
python -m tr_to_finary.cli --fetch

# Fetch + sync + auto-approve
python -m tr_to_finary.cli --fetch --execute --yes

# From CSV + preview
python -m tr_to_finary.cli export.csv

# From CSV + sync to specific account
python -m tr_to_finary.cli export.csv --account "TR Invest" --execute

# Just inspect transactions
python -m tr_to_finary.cli export.csv --parse-only --trades-only

# Force full re-sync
python -m tr_to_finary.cli --fetch --reset --execute
```

## How it works

```
Trade Republic CSV          Finary
  or pytr fetch      ->    positions
                           via API

1. Parse CSV (auto-detect format)
2. Filter BUY/SELL/DIVIDEND transactions
3. Aggregate into positions (per ISIN)
   - Weighted average buy price
   - Net quantity after sells
4. Compare with sync state (.sync_state.json)
5. Create or update positions in Finary
```

## Duplicate protection

- Each transaction has a unique ID (from TR or generated from pytr data)
- `.sync_state.json` tracks which transactions have been synced
- Re-running the same CSV does nothing
- New transactions trigger position updates with recalculated averages
- Interactive confirmation before each update (unless `--yes`)

## Files

| File | Description |
|------|-------------|
| `credentials.json` | Finary email + password (not committed) |
| `.sync_state.json` | Tracks synced transaction IDs (not committed) |
| `~/.pytr/credentials` | Trade Republic phone + PIN (managed by pytr) |

## Requirements

- Python >= 3.10
- [finary-uapi](https://github.com/lasconic/finary_uapi) - Finary unofficial API
- [pytr](https://github.com/pytr-org/pytr) - Trade Republic CLI (optional, for --fetch)
- [rich](https://github.com/Textualize/rich) - Terminal formatting

## Limitations

- Finary API is unofficial and may change
- Trade Republic's CSV format may change
- 2FA is required for Finary (TOTP supported)
- pytr requires Playwright for AWS WAF token

## License

MIT
