#!/usr/bin/env python3
"""
FRED（圣路易斯联储）数据获取脚本

用法：
    python get_fred.py --series CPIAUCSL --start 2010 --end 2023

需要 FRED_API_KEY 环境变量（在设置面板填入，或 .env 文件中设置）。
免费注册：https://fred.stlouisfed.org/docs/api/api_key.html

常用序列：
    CPIAUCSL  - 美国 CPI（季节调整）
    UNRATE    - 美国失业率
    GDP       - 美国实际 GDP
    FEDFUNDS  - 联邦基金利率

输出：JSON 摘要 + CSV 保存到 /workspace/data/
"""
import argparse
import json
import os
import sys


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


def main():
    parser = argparse.ArgumentParser(description="Fetch FRED data")
    parser.add_argument("--series", required=True, help="FRED series ID (e.g., CPIAUCSL)")
    parser.add_argument("--start", default="2010-01-01", help="Start date (YYYY-MM-DD or YYYY)")
    parser.add_argument("--end", default="2023-12-31", help="End date (YYYY-MM-DD or YYYY)")
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print(json.dumps({
            "error": "未找到 FRED_API_KEY 环境变量。请在设置面板填入 FRED API Key（免费注册：https://fred.stlouisfed.org/docs/api/api_key.html）"
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        import fredapi
    except ImportError:
        _auto_install("fredapi")
        import fredapi

    # 处理年份格式
    start_date = args.start if "-" in args.start else f"{args.start}-01-01"
    end_date = args.end if "-" in args.end else f"{args.end}-12-31"

    try:
        fred = fredapi.Fred(api_key=api_key)
        series = fred.get_series(args.series, observation_start=start_date, observation_end=end_date)
    except Exception as e:
        print(json.dumps({"error": f"FRED API 请求失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    if series is None or len(series) == 0:
        print(json.dumps({"error": "未获取到数据，请检查序列代码"}, ensure_ascii=False))
        sys.exit(1)

    # 保存 CSV
    output_dir = _resolve_workspace()
    os.makedirs(output_dir, exist_ok=True)
    start_year = start_date[:4]
    end_year = end_date[:4]
    filename = f"fred_{args.series}_{start_year}_{end_year}.csv"
    filepath = os.path.join(output_dir, filename)

    try:
        df = series.reset_index()
        df.columns = ["date", "value"]
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
    except Exception as e:
        print(json.dumps({"error": f"CSV 保存失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    summary = {
        "source": "FRED（圣路易斯联储）",
        "series": args.series,
        "rows": len(series),
        "date_range": f"{series.index[0].date()} ~ {series.index[-1].date()}",
        "csv_path": f"/workspace/data/{filename}",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
