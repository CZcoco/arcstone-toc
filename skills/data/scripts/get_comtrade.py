#!/usr/bin/env python3
"""
UN Comtrade 国际贸易数据获取脚本

用法：
    python get_comtrade.py --reporter 156 --partner 842 --year 2023

常用国家代码（M49）：
    156  中国
    842  美国（注意：UN Comtrade 用 842，不是 840）
    276  德国
    392  日本
    410  韩国
    0    世界（所有贸易伙伴汇总）

注意：UN Comtrade API 有频率限制（未注册用户每小时约5次）。
如遇 429 错误，等待一小时后重试，或注册获取 API Key（免费）：
    https://comtradeplus.un.org/

输出：JSON 摘要 + CSV 保存到 /workspace/data/
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.parse


def _resolve_workspace() -> str:
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        )))))
        from src.tools.path_resolver import resolve_virtual_path
        return resolve_virtual_path("/workspace/data/")
    except Exception:
        fallback = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "data", "workspace", "data")
        return os.path.normpath(fallback)


def _auto_install(package: str):
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", package, "-q"], check=False)


def fetch_comtrade(reporter: str, partner: str, year: int) -> list[dict]:
    """
    使用 UN Comtrade Legacy API（免费，无需 key，但有频率限制）获取年度贸易数据。
    """
    url = (
        f"https://comtradeapi.un.org/public/v1/preview/C/A/HS"
        f"?reporterCode={reporter}&partnerCode={partner}&period={year}"
        f"&cmdCode=TOTAL&flowCode=X,M&maxRecords=500"
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "EconAgent/1.0", "Accept": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 429:
                return [{"error": "API 频率限制（429），请等待1小时后重试，或注册 API Key"}]
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        # Fallback to legacy API
        return _fetch_comtrade_legacy(reporter, partner, year)

    results = []
    for item in data.get("data", []):
        results.append({
            "period": item.get("period"),
            "reporter": item.get("reporterDesc", reporter),
            "partner": item.get("partnerDesc", partner),
            "flow": item.get("flowDesc", ""),
            "commodity": item.get("cmdDesc", "TOTAL"),
            "trade_value_usd": item.get("primaryValue", 0),
        })
    return results


def _fetch_comtrade_legacy(reporter: str, partner: str, year: int) -> list[dict]:
    """降级到旧版 Comtrade API。"""
    url = (
        f"https://comtrade.un.org/api/get"
        f"?type=C&freq=A&px=HS&ps={year}"
        f"&r={reporter}&p={partner}"
        f"&rg=all&cc=TOTAL&fmt=json&max=500"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "EconAgent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return [{"error": f"Comtrade Legacy API 请求失败: {e}"}]

    results = []
    for item in data.get("dataset", []):
        results.append({
            "period": item.get("yr"),
            "reporter": item.get("rtTitle", reporter),
            "partner": item.get("ptTitle", partner),
            "flow": item.get("rgDesc", ""),
            "commodity": item.get("cmdDescE", "TOTAL"),
            "trade_value_usd": item.get("TradeValue", 0),
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="Fetch UN Comtrade trade data")
    parser.add_argument("--reporter", required=True, help="Reporter country M49 code (e.g., 156 for China)")
    parser.add_argument("--partner", default="0", help="Partner country M49 code (0=World)")
    parser.add_argument("--year", type=int, default=2022, help="Year (default: 2022)")
    args = parser.parse_args()

    rows = fetch_comtrade(args.reporter, args.partner, args.year)

    if rows and "error" in rows[0]:
        print(json.dumps(rows[0], ensure_ascii=False))
        sys.exit(1)

    if not rows:
        print(json.dumps({"error": "未获取到数据"}, ensure_ascii=False))
        sys.exit(1)

    # 保存 CSV
    output_dir = _resolve_workspace()
    os.makedirs(output_dir, exist_ok=True)
    filename = f"comtrade_{args.reporter}_{args.partner}_{args.year}.csv"
    filepath = os.path.join(output_dir, filename)

    try:
        import csv
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
    except Exception as e:
        print(json.dumps({"error": f"CSV 保存失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    total_export = sum(r.get("trade_value_usd", 0) for r in rows if "export" in r.get("flow", "").lower() or "X" in r.get("flow", ""))
    summary = {
        "source": "UN Comtrade",
        "reporter": args.reporter,
        "partner": args.partner,
        "year": args.year,
        "rows": len(rows),
        "csv_path": f"/workspace/data/{filename}",
        "preview": rows[:3],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
