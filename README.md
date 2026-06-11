# TradeRepublic to Finary

Sync your **Trade Republic** **portfolio** to **[Finary](https://finary.com)** automatically.

> Finary's Trade Republic provider is broken? No worries. This tool reads your TR transactions and syncs your positions to Finary via its API.

## Features

- **Web UI**: clean dashboard with sync workflow, transaction browser, and settings
- **CLI**: full-featured command line interface with Rich terminal UI
- **Two data sources**: manual CSV export from TR app, or automatic fetch via [pytr](https://github.com/pytr-org/pytr)
- **Smart sync**: only new transactions are processed (tracked via `.sync_state.json`)
- **Position aggregation**: computes weighted average buy price from all your trades
- **Dividend tracking**: dividends are tracked per position
- **Multi-format**: auto-detects Trade Republic native CSV and pytr CSV formats

## Quick Start (Windows)

### Option A: One-click install

1. Download the project
2. Double-click **`install.bat`** to install all dependencies
3. Run `python -m tr_to_finary.cli --setup` to configure credentials
4. Double-click **`start.bat`** to launch the Web UI

### Option B: Manual install

```bash
pip install finary-uapi pytr rich fastapi "uvicorn[standard]" jinja2 python-multipart
python -m playwright install chromium
```

## Web UI

Launch the web interface:

```bash
python -m tr_to_finary.web
```

Or double-click `start.bat`. Opens automatically at **http://127.0.0.1:8000**

**Pages:**
- **Dashboard** — sync status, positions overview, quick actions
- **Sync** — upload CSV or fetch from TR, preview positions, sync to Finary
- **Transactions** — browse all parsed transactions with filters
- **Settings** — configure account name, view credentials status, reset sync state

## CLI Usage

```bash
python -m tr_to_finary.cli --setup                    # First-time setup wizard
python -m tr_to_finary.cli --fetch                     # Fetch from TR + preview
python -m tr_to_finary.cli --fetch --execute           # Fetch + sync to Finary
python -m tr_to_finary.cli --fetch --execute --yes     # Fetch + sync (auto-approve)
python -m tr_to_finary.cli export.csv --execute        # From manual CSV export
python -m tr_to_finary.cli export.csv --parse-only     # Just inspect transactions
python -m tr_to_finary.cli --fetch --reset --execute   # Force full re-sync
```

### CLI Options

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
- [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) - Web UI

## License

MIT
