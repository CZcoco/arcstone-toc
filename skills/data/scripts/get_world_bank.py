#!/usr/bin/env python3
"""
World Bank 数据获取脚本（使用 wbgapi）

用法：
    python get_world_bank.py --indicator NY.GDP.MKTP.CD --countries "CN US" --start 2000 --end 2023

常用指标：
    NY.GDP.MKTP.CD   - GDP（当前美元）
    NY.GDP.PCAP.CD   - 人均 GDP
    SL.UEM.TOTL.ZS   - 失业率
    IT.NET.USER.ZS   - 互联网用户占比

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
    parser = argparse.ArgumentParser(description="Fetch World Bank data")
    parser.add_argument("--indicator", required=True, help="WB indicator code")
    parser.add_argument("--countries", default="CN", help="Space-separated ISO2 codes (e.g., 'CN US')")
    parser.add_argument("--start", type=int, default=2000)
    parser.add_argument("--end", type=int, default=2023)
    args = parser.parse_args()

    try:
        import wbgapi
    except ImportError:
        _auto_install("wbgapi")
        import wbgapi

    country_list = args.countries.split()

    try:
        df = wbgapi.data.DataFrame(
            args.indicator,
            economy=country_list,
            time=range(args.start, args.end + 1),
            labels=True,
        )
    except Exception as e:
        print(json.dumps({"error": f"World Bank API 请求失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    if df.empty:
        print(json.dumps({"error": "未获取到数据，请检查指标代码或国家代码"}, ensure_ascii=False))
        sys.exit(1)

    # 整理为长格式
    df = df.reset_index()
    # wbgapi DataFrame columns: economy label, time, value
    # Reshape if needed
    df.columns = [str(c) for c in df.columns]

    # 保存 CSV
    output_dir = _resolve_workspace()
    os.makedirs(output_dir, exist_ok=True)
    countries_str = "_".join(country_list)
    filename = f"wb_{args.indicator.replace('.', '_')}_{countries_str}_{args.start}_{args.end}.csv"
    filepath = os.path.join(output_dir, filename)

    try:
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
    except Exception as e:
        print(json.dumps({"error": f"CSV 保存失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    summary = {
        "source": "World Bank",
        "indicator": args.indicator,
        "countries": country_list,
        "rows": len(df),
        "columns": list(df.columns),
        "years": f"{args.start}-{args.end}",
        "csv_path": f"/workspace/data/{filename}",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
