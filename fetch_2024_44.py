"""
Download 2024 Angel One 15-minute data for our NSE universe.

DATA ONLY:
- No strategy
- No backtest
- No orders
- No credentials printed
"""

import json
import os
import sqlite3
import time
import urllib.request
from pathlib import Path

import pyotp
from SmartApi import SmartConnect
from sector_map import SECTOR_MAP


DB = "data/intraday_ohlcv.db"

SCRIP_URL = (
    "https://margincalculator.angelbroking.com/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)

# 2024 ONLY
WINDOWS = [
    ("2024-01-01 09:15", "2024-03-31 15:15"),
    ("2024-04-01 09:15", "2024-06-30 15:15"),
    ("2024-07-01 09:15", "2024-09-30 15:15"),
    ("2024-10-01 09:15", "2024-12-31 15:15"),
]

# These are not currently usable members of our active universe.
SKIP = {
    "HDFC",
    "TATAMOTORS",
}

ALIAS = {
    "M_M": "M&M",
}


def load_env():
    p = Path(".env")

    if not p.exists():
        raise SystemExit("CREDENTIALS_MISSING")

    for raw in p.read_text().splitlines():
        line = raw.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip()
        )


def get_universe():
    symbols = []

    for raw_symbol in SECTOR_MAP:
        symbol = (
            str(raw_symbol)
            .replace(".NS", "")
            .replace("-EQ", "")
            .strip()
        )

        if symbol in SKIP:
            continue

        symbol = ALIAS.get(symbol, symbol)

        if symbol not in symbols:
            symbols.append(symbol)

    return symbols


def load_tokens(symbols):
    print("Loading Angel scrip master...")

    with urllib.request.urlopen(
        SCRIP_URL,
        timeout=60
    ) as response:

        data = json.loads(
            response.read().decode("utf-8")
        )

    wanted = {
        s.upper()
        for s in symbols
    }

    result = {}

    for row in data:

        if row.get("exch_seg") != "NSE":
            continue

        symbol = str(
            row.get("symbol") or ""
        )

        if not symbol.endswith("-EQ"):
            continue

        base = symbol[:-3]

        if base.upper() in wanted:
            result[base.upper()] = str(
                row.get("token")
            )

    return result


def angel_login():

    api_key = os.getenv(
        "ANGEL_API_KEY"
    )

    client_id = os.getenv(
        "ANGEL_CLIENT_ID"
    )

    password = os.getenv(
        "ANGEL_PASSWORD"
    )

    totp_secret = os.getenv(
        "ANGEL_TOTP_SECRET"
    )

    if not all([
        api_key,
        client_id,
        password,
        totp_secret
    ]):
        raise SystemExit(
            "CREDENTIALS_MISSING"
        )

    obj = SmartConnect(
        api_key=api_key
    )

    totp = pyotp.TOTP(
        totp_secret
    ).now()

    obj.generateSession(
        client_id,
        password,
        totp
    )

    return obj


def init_database():

    Path("data").mkdir(
        exist_ok=True
    )

    con = sqlite3.connect(DB)

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS intraday_ohlcv (
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,

            PRIMARY KEY (
                symbol,
                interval,
                timestamp
            )
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_2024_progress (
            symbol TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            status TEXT NOT NULL,
            rows INTEGER NOT NULL DEFAULT 0,

            PRIMARY KEY (
                symbol,
                window_start,
                window_end
            )
        )
        """
    )

    con.commit()

    return con


def chunk_done(
    con,
    symbol,
    start,
    end
):

    row = con.execute(
        """
        SELECT status

        FROM fetch_2024_progress

        WHERE symbol=?
        AND window_start=?
        AND window_end=?
        """,

        (
            symbol,
            start,
            end
        )
    ).fetchone()

    return bool(
        row
        and row[0] == "DONE"
    )


def mark_progress(
    con,
    symbol,
    start,
    end,
    status,
    rows
):

    con.execute(
        """
        INSERT OR REPLACE
        INTO fetch_2024_progress
        (
            symbol,
            window_start,
            window_end,
            status,
            rows
        )

        VALUES (
            ?, ?, ?, ?, ?
        )
        """,

        (
            symbol,
            start,
            end,
            status,
            rows
        )
    )

    con.commit()


def save_rows(
    con,
    symbol,
    rows
):

    count = 0

    for row in rows:

        try:

            timestamp = (
                str(row[0])
                .replace("T", " ")[:19]
            )

            hhmm = timestamp[11:16]

            if not (
                "09:15"
                <= hhmm
                <= "15:15"
            ):
                continue

            o = float(row[1])
            h = float(row[2])
            l = float(row[3])
            c = float(row[4])

            volume = int(
                float(row[5])
            )

            if min(
                o, h, l, c
            ) <= 0:
                continue

            if volume < 0:
                continue

            con.execute(
                """
                INSERT OR REPLACE
                INTO intraday_ohlcv
                (
                    symbol,
                    interval,
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,

                (
                    symbol,
                    "15m",
                    timestamp,
                    o,
                    h,
                    l,
                    c,
                    volume
                )
            )

            count += 1

        except Exception:
            continue

    con.commit()

    return count


def fetch_chunk(
    obj,
    token,
    start,
    end
):

    # Conservative retries because Angel
    # rate-limited us in earlier downloads.
    waits = [
        0,
        10,
        20,
        40,
        60
    ]

    for attempt, wait_seconds in enumerate(
        waits,
        start=1
    ):

        if wait_seconds:

            print(
                f"    retry wait "
                f"{wait_seconds}s"
            )

            time.sleep(
                wait_seconds
            )

        try:

            result = obj.getCandleData(
                {
                    "exchange": "NSE",

                    "symboltoken":
                        token,

                    "interval":
                        "FIFTEEN_MINUTE",

                    "fromdate":
                        start,

                    "todate":
                        end,
                }
            )

            rows = (
                (result or {})
                .get("data")
                or []
            )

            return rows, True

        except Exception:

            # Do not print the raw SDK exception.
            # It may expose authorization headers.
            print(
                "    request failed "
                f"attempt "
                f"{attempt}/"
                f"{len(waits)}"
            )

    return [], False


def print_coverage(con):

    print("\n2024 COVERAGE")

    rows = con.execute(
        """
        SELECT
            symbol,
            MIN(timestamp),
            MAX(timestamp),
            COUNT(*)

        FROM intraday_ohlcv

        WHERE interval='15m'
        AND substr(
            timestamp,
            1,
            4
        )='2024'

        GROUP BY symbol

        ORDER BY symbol
        """
    ).fetchall()

    for row in rows:
        print(row)

    failed_chunks = con.execute(
        """
        SELECT COUNT(*)

        FROM fetch_2024_progress

        WHERE status='FAILED'
        """
    ).fetchone()[0]

    print(
        "symbols_with_2024_data",
        len(rows)
    )

    print(
        "failed_chunks",
        failed_chunks
    )


def main():

    load_env()

    symbols = get_universe()

    print(
        "2024_15M_FETCH"
    )

    print(
        "NO ORDERS / DATA ONLY"
    )

    print(
        "symbols",
        len(symbols),
        "windows",
        len(WINDOWS)
    )

    token_map = load_tokens(
        symbols
    )

    obj = angel_login()

    con = init_database()

    total = len(symbols)

    for symbol_number, symbol in enumerate(
        symbols,
        start=1
    ):

        token = token_map.get(
            symbol.upper()
        )

        if not token:

            print(
                f"[{symbol_number}/{total}] "
                f"{symbol}: NO_TOKEN"
            )

            continue

        for window_number, (
            start,
            end
        ) in enumerate(
            WINDOWS,
            start=1
        ):

            if chunk_done(
                con,
                symbol,
                start,
                end
            ):

                print(
                    f"[{symbol_number}/{total}] "
                    f"{symbol} "
                    f"W{window_number}: "
                    "SKIP_DONE"
                )

                continue

            print(
                f"[{symbol_number}/{total}] "
                f"{symbol} "
                f"W{window_number}: "
                "fetching"
            )

            # Keep request rate conservative.
            time.sleep(5)

            rows, success = fetch_chunk(
                obj,
                token,
                start,
                end
            )

            if not success:

                mark_progress(
                    con,
                    symbol,
                    start,
                    end,
                    "FAILED",
                    0
                )

                print(
                    "    FAILED"
                )

                continue

            saved = save_rows(
                con,
                symbol,
                rows
            )

            mark_progress(
                con,
                symbol,
                start,
                end,
                "DONE",
                saved
            )

            print(
                f"    DONE rows="
                f"{saved}"
            )

    print_coverage(
        con
    )

    con.close()

    print(
        "\nFETCH_2024_COMPLETE"
    )

    print(
        "NO ORDERS / NO BACKTEST"
    )


if __name__ == "__main__":
    main()