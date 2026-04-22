#!/usr/bin/env python3
"""Fetch hotel vacancies and notify Telegram."""

from __future__ import annotations
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_QUERY = {
    "hotelId": "0000000201",
    "adult": "2",
    "underTwelve": "0",
    "underFour": "0",
    "stayLength": "5",
    "monthlyDate": "2027%2F02%2F01",
    "lang": "CH",
    "_":"1776783640791"
}


def getenv_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def fetch_json(url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params)}"

    print(f"[DEBUG] Request URL: {full_url}")

    req = Request(full_url, headers={"User-Agent": "vacancy-monitor/1.0"})

    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            print(f"[DEBUG] Response status: {resp.status}")
            print(f"[DEBUG] Response body (first 500 chars): {body[:500]}")
            return json.loads(body)

    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"[DEBUG] HTTPError status: {exc.code}", file=sys.stderr)
        print(f"[DEBUG] HTTPError URL: {full_url}", file=sys.stderr)
        print(f"[DEBUG] HTTPError body (first 500 chars): {error_body[:500]}", file=sys.stderr)
        raise

    except URLError as exc:
        print(f"[DEBUG] URLError URL: {full_url}", file=sys.stderr)
        print(f"[DEBUG] URLError reason: {exc.reason}", file=sys.stderr)
        raise


def parse_target_dates(raw_dates: str) -> list[str]:
    result: list[str] = []
    for item in raw_dates.split(","):
        date_str = item.strip()
        if not date_str:
            continue
        datetime.strptime(date_str, "%Y-%m-%d")
        result.append(date_str)
    if not result:
        raise RuntimeError("TARGET_DATES is empty")
    return result


def twd_rate_per_jpy() -> Decimal:
    data = fetch_json(
        "https://api.frankfurter.dev/v2/rates",
        {"base": "JPY", "quotes": "TWD"},
    )
    print(f"[DEBUG] FX payload: {data}")
    rate = data.get("rates", {}).get("TWD")
    if rate is None:
        raise RuntimeError("Unable to fetch JPY->TWD exchange rate")
    return Decimal(str(rate))

def group_dates_by_month(target_dates: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for date in target_dates:
        dt = datetime.strptime(date, "%Y-%m-%d")
        month_key = dt.strftime("%Y/%m/01")
        grouped[month_key].append(dt.strftime("%Y/%m/%d"))
    return grouped


def fetch_vacancy_map(api_url: str, target_dates: list[str]) -> dict[str, dict[str, Any]]:
    grouped = group_dates_by_month(target_dates)
    output: dict[str, dict[str, Any]] = {}

    for monthly_date, wanted_dates in grouped.items():
        params = dict(DEFAULT_QUERY)
        params["monthlyDate"] = monthly_date
        params["_"] = str(int(datetime.now().timestamp() * 1000))
        payload = fetch_json(api_url, params)

        items = payload.get("vacancyList", [])
        for item in items:
            date = item.get("date")
            if date in wanted_dates:
                output[date] = item
    return output


def build_message(target_dates: list[str], vacancies: dict[str, dict[str, Any]], rate: Decimal) -> str:
    lines = ["🏨 飯店訂房監控結果"]
    available_lines: list[str] = []

    for date_iso in target_dates:
        date_slash = datetime.strptime(date_iso, "%Y-%m-%d").strftime("%Y/%m/%d")
        item = vacancies.get(date_slash)
        if not item:
            available_lines.append(f"- {date_iso}：查無資料")
            continue

        vacancy = int(item.get("vacancy", 0))
        if vacancy <= 0:
            available_lines.append(f"- {date_iso}：目前沒空房")
            continue

        jpy = Decimal(str(item.get("charge", {}).get("searchChargeDetail", {}).get("unitCharge", 0)))
        twd = (jpy * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        available_lines.append(
            f"- {date_iso}：有空房 {vacancy} 間，價格 JPY {jpy:,}（約 TWD {twd:,}）"
        )

    if all("目前沒空房" in line for line in available_lines if "查無資料" not in line):
        lines.append("目標日期目前沒空房。")

    lines.extend(available_lines)
    lines.append(f"匯率：1 JPY ≈ {rate} TWD")
    return "\n".join(lines)


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = Request(api, data=payload, method="POST")
    with urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API error: {body}")


def main() -> int:
    api_url = getenv_required("API_URL")
    bot_token = getenv_required("TELEGRAM_BOT_TOKEN")
    chat_id = getenv_required("TELEGRAM_CHAT_ID")
    target_dates = parse_target_dates(
        os.getenv("TARGET_DATES", "2026-02-15,2026-02-28")
    )

    rate = twd_rate_per_jpy()
    vacancies = fetch_vacancy_map(api_url, target_dates)
    message = build_message(target_dates, vacancies, rate)
    send_telegram_message(bot_token, chat_id, message)
    print("Message sent to Telegram")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
