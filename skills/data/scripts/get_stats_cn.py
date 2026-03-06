#!/usr/bin/env python3
"""
国家统计局（NBS）数据获取脚本

用法：
    python get_stats_cn.py --indicator A010101 --start 2010 --end 2023

指标代码示例：
    A010101 - 国内生产总值（亿元）
    A010201 - 人均国内生产总值（元）
    A020101 - 居民消费价格指数
    A030201 - 城镇居民人均可支配收入

NBS API（免费，无需 key）：
    https://data.stats.gov.cn/easyquery.htm（网页版）
    通过 requests 模拟请求

输出：JSON 摘要 + CSV 保存到 /workspace/data/
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.parse


def _resolve_workspace() -> str:
    """获取真实工作区路径。"""
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


def fetch_nbs_data(indicator: str, start: int, end: int) -> list[dict]:
    """
    从国家统计局 EasyQuery API 获取数据。
    API 文档：https://data.stats.gov.cn/easyquery.htm
    """
    try:
        import requests
    except ImportError:
        _auto_install("requests")
        import requests

    url = "https://data.stats.gov.cn/easyquery.htm"
    params = {
        "m": "QueryData",
        "dbcode": "hgnd",  # 宏观年度数据库
        "rowcode": "zb",
        "colcode": "sj",
        "wds": "[]",
        "dfwds": json.dumps([{"wdcode": "zb", "valuecode": indicator}]),
        "k1": "1",
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://data.stats.gov.cn/",
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return [{"error": f"NBS API 请求失败: {e}"}]

    # 解析返回数据
    rows = []
    try:
        datanodes = data.get("returndata", {}).get("datanodes", [])
        for node in datanodes:
            wds = {w["wdcode"]: w["valuecode"] for w in node.get("wds", [])}
            year_str = wds.get("sj", "")
            value = node.get("data", {}).get("strdata", "")

            if not year_str or not year_str.isdigit():
                continue
            year = int(year_str)
            if start <= year <= end:
                try:
                    val = float(value)
                except (ValueError, TypeError):
                    val = None
                rows.append({"year": year, "value": val, "indicator": indicator})
    except Exception as e:
        return [{"error": f"数据解析失败: {e}"}]

    rows.sort(key=lambda x: x["year"])
    return rows


def main():
    parser = argparse.ArgumentParser(description="Fetch data from China NBS")
    parser.add_argument("--indicator", required=True, help="Indicator code (e.g., A010101)")
    parser.add_argument("--start", type=int, default=2010)
    parser.add_argument("--end", type=int, default=2023)
    args = parser.parse_args()

    rows = fetch_nbs_data(args.indicator, args.start, args.end)

    if rows and "error" in rows[0]:
        print(json.dumps(rows, ensure_ascii=False))
        sys.exit(1)

    if not rows:
        print(json.dumps({"error": "未获取到数据，请检查指标代码是否正确"}, ensure_ascii=False))
        sys.exit(1)

    # 保存 CSV
    output_dir = _resolve_workspace()
    os.makedirs(output_dir, exist_ok=True)
    filename = f"nbs_{args.indicator}_{args.start}_{args.end}.csv"
    filepath = os.path.join(output_dir, filename)

    try:
        import csv
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["year", "indicator", "value"])
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        print(json.dumps({"error": f"CSV 保存失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    summary = {
        "source": "NBS（国家统计局）",
        "indicator": args.indicator,
        "rows": len(rows),
        "years": f"{args.start}-{args.end}",
        "csv_path": f"/workspace/data/{filename}",
        "preview": rows[:3],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
