"""Interactive setup wizard for first-time users."""

import json
import subprocess
import sys
from pathlib import Path

from rich.panel import Panel

from .ui import console, print_banner, print_step, print_success, print_error, print_warning, print_info


def check_pytr_installed() -> bool:
    try:
        import pytr
        return True
    except ImportError:
        return False


def check_pytr_credentials() -> bool:
    cred_path = Path.home() / ".pytr" / "credentials"
    return cred_path.exists()


def check_finary_credentials() -> bool:
    return Path("credentials.json").exists()


def check_finary_uapi_installed() -> bool:
    try:
        import finary_uapi
        return True
    except ImportError:
        return False


def check_playwright() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


def run_setup():
    """Interactive setup wizard."""
    print_banner()

    console.print("\n[bold]Welcome! This wizard will help you set up TR → Finary sync.[/]\n")

    # Step 1: Check dependencies
    print_step(1, "Checking dependencies")

    all_good = True

    if check_finary_uapi_installed():
        print_success("finary-uapi installed")
    else:
        print_error("finary-uapi not installed")
        console.print("    Run: [bold cyan]pip install finary-uapi[/]")
        all_good = False

    if check_pytr_installed():
        print_success("pytr installed")
    else:
        print_warning("pytr not installed (optional, needed for --fetch)")
        console.print("    Run: [bold cyan]pip install pytr[/]")

    # Step 2: Finary credentials
    print_step(2, "Finary credentials")

    if check_finary_credentials():
        print_success("credentials.json found")
    else:
        console.print("  Finary needs your email and password to sync.\n")

        email = console.input("  [bold]Finary email:[/] ").strip()
        password = console.input("  [bold]Finary password:[/] ", password=True).strip()

        if email and password:
            creds = {"email": email, "password": password}
            Path("credentials.json").write_text(
                json.dumps(creds, indent=2), encoding="utf-8"
            )
            print_success("credentials.json created")
        else:
            print_error("Skipped — you'll need to create credentials.json manually")
            all_good = False

    # Step 3: Test Finary login
    print_step(3, "Testing Finary connection")

    try:
        from finary_uapi.signin import signin

        try:
            result = signin()
            status = result.get("response", {}).get("status", "")
        except RuntimeError as e:
            if "OTP" in str(e):
                console.print("  [yellow]2FA is enabled on your Finary account.[/]")
                otp = console.input("  [bold]Enter your 2FA code:[/] ").strip()
                result = signin(otp_code=otp)
                status = result.get("response", {}).get("status", "")
            else:
                raise

        if status == "complete":
            print_success("Finary login successful!")
        else:
            print_error(f"Finary login failed (status: {status})")
            all_good = False
    except Exception as e:
        print_error(f"Finary login failed: {e}")
        all_good = False

    # Step 4: Trade Republic (pytr) setup
    print_step(4, "Trade Republic setup (pytr)")

    if not check_pytr_installed():
        print_warning("pytr not installed — skipping TR setup")
        print_info("You can still use manual CSV export from the TR app")
    elif check_pytr_credentials():
        print_success("pytr credentials found")
        console.print("  [dim]Testing connection...[/]")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytr", "portfolio"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                print_success("Trade Republic connection works!")
            else:
                print_warning("Could not connect to TR — you may need to re-login")
                print_info("Run: python -m pytr login --store_credentials")
        except Exception:
            print_warning("Could not test TR connection")
    else:
        console.print("  pytr needs to log in to Trade Republic.\n")
        do_login = console.input("  [bold]Set up TR login now? [Y/n][/] ").strip().lower()
        if do_login != "n":
            console.print("\n  [dim]This will open an interactive login...[/]\n")
            subprocess.run([
                sys.executable, "-m", "pytr", "login", "--store_credentials"
            ])
            if check_pytr_credentials():
                print_success("Trade Republic login configured!")
            else:
                print_warning("Login may have failed — try again later")
        else:
            print_info("Skipped — run 'python -m pytr login --store_credentials' later")

    # Summary
    print_step(5, "Setup complete!")

    if all_good:
        console.print(Panel(
            "[bold green]Everything is configured![/]\n\n"
            "Quick start:\n"
            "  [cyan]python -m tr_to_finary.cli --fetch[/]           Fetch from TR + dry run\n"
            "  [cyan]python -m tr_to_finary.cli --fetch --execute[/] Fetch + sync to Finary\n"
            "  [cyan]python -m tr_to_finary.cli export.csv[/]        From manual CSV export",
            title="Ready to go!",
            border_style="green",
        ))
    else:
        console.print(Panel(
            "[bold yellow]Some steps need attention.[/]\n"
            "Fix the issues above and run [cyan]--setup[/] again.",
            title="Almost there",
            border_style="yellow",
        ))
