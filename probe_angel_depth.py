"""Angel 15-minute history depth probe. No orders. Never print secrets."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path("output")
ENV_NAMES = [
    "ANGEL_API_KEY",
    "ANGEL_CLIENT_ID",
    "ANGEL_PASSWORD",
    "ANGEL_TOTP",
    "ANGEL_TOTP_SECRET",
]


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def status(name: str) -> str:
    return "SET" if os.getenv(name) else "MISSING"


def write_report(text: str) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "angel_depth_probe.md").write_text(text, encoding="utf-8")
    print(text)


def main() -> int:
    load_env(Path(".env"))
    banner = [
        "PHASE 0b DEPTH PROBE",
        "No orders. Secrets not printed.",
        "Env: " + ", ".join(f"{n}={status(n)}" for n in ENV_NAMES),
        "",
    ]
    if not os.getenv("ANGEL_API_KEY") or not os.getenv("ANGEL_CLIENT_ID"):
        write_report("\n".join(banner + ["STATUS: CREDENTIALS_MISSING", "180-day: NO"]))
        return 0

    password = os.getenv("ANGEL_PASSWORD") or ""
    totp_secret = os.getenv("ANGEL_TOTP_SECRET") or ""
    totp_code = os.getenv("ANGEL_TOTP") or ""
    try:
        from SmartApi import SmartConnect
    except Exception as exc:
        write_report("\n".join(banner + [f"STATUS: IMPORT_FAIL {exc}", "180-day: NO"]))
        return 1

    if totp_secret:
        try:
            import pyotp

            totp_code = pyotp.TOTP(totp_secret).now()
        except Exception as exc:
            write_report("\n".join(banner + [f"STATUS: TOTP_FAIL {exc}", "180-day: NO"]))
            return 1
    if not totp_code:
        write_report("\n".join(banner + ["STATUS: TOTP_MISSING (need ANGEL_TOTP_SECRET)", "180-day: NO"]))
        return 0

    try:
        obj = SmartConnect(api_key=os.environ["ANGEL_API_KEY"])
        obj.generateSession(os.environ["ANGEL_CLIENT_ID"], password, totp_code)
    except Exception as exc:
        write_report("\n".join(banner + [f"STATUS: LOGIN_FAIL {exc}", "180-day: NO"]))
        return 1

    to_dt = datetime.now()
    from_dt = to_dt - timedelta(days=365)
    params = {
        "exchange": "NSE",
        "symboltoken": "2885",
        "interval": "FIFTEEN_MINUTE",
        "fromdate": from_dt.strftime("%Y-%m-%d 09:15"),
        "todate": to_dt.strftime("%Y-%m-%d 15:30"),
    }
    try:
        raw = obj.getCandleData(params)
        rows = (raw or {}).get("data") or []
    except Exception as exc:
        write_report("\n".join(banner + [f"STATUS: CANDLE_FAIL {exc}", "180-day: NO"]))
        return 1

    if not rows:
        write_report("\n".join(banner + ["STATUS: LOGIN_OK EMPTY_CANDLES", "180-day: NO"]))
        return 0

    first, last = str(rows[0][0]), str(rows[-1][0])
    try:
        d0 = datetime.fromisoformat(first.replace("T", " ")[:19])
        d1 = datetime.fromisoformat(last.replace("T", " ")[:19])
        days = (d1 - d0).days
    except Exception:
        days = -1
    yes180 = "YES" if days >= 180 else "NO"
    write_report(
        "\n".join(
            banner
            + [
                "STATUS: LOGIN_OK",
                f"symbol: RELIANCE token 2885",
                f"bars: {len(rows)}",
                f"first: {first}",
                f"last: {last}",
                f"calendar_days_span: {days}",
                f"180-day: {yes180}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
