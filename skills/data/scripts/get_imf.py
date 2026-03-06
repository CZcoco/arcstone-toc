#!/usr/bin/env python3
"""
IMF 数据获取脚本（使用 imfp）

用法：
    python get_imf.py --dataset IFS --indicator NGDP_RPCH --country CN

常用 Dataset：
    IFS   - 国际金融统计
    WEO   - 世界经济展望
    BOP   - 国际收支

常用指标（IFS）：
    NGDP_RPCH   - 实际 GDP 增速（%）
    PCPI_IX     - 消费者价格指数
    BCA_NGDPD   - 经常账户余额占 GDP

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
    parser = argparse.ArgumentParser(description="Fetch IMF data via imfp")
    parser.add_argument("--dataset", default="IFS", help="IMF dataset (default: IFS)")
    parser.add_argument("--indicator", required=True, help="Indicator code (e.g., NGDP_RPCH)")
    parser.add_argument("--country", default="CN", help="ISO2 country code (default: CN)")
    parser.add_argument("--start", type=int, default=2000)
    parser.add_argument("--end", type=int, default=2023)
    args = parser.parse_args()

    try:
        import imfp
    except ImportError:
        _auto_install("imfp")
        import imfp

    try:
        df = imfp.imf_dataset(
            database_id=args.dataset,
            indicator=args.indicator,
            ref_area=args.country,
            start_year=args.start,
            end_year=args.end,
        )
    except Exception as e:
        print(json.dumps({"error": f"IMF API 请求失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    if df is None or df.empty:
        print(json.dumps({"error": "未获取到数据，请检查数据集/指标/国家代码"}, ensure_ascii=False))
        sys.exit(1)

    # 保存 CSV
    output_dir = _resolve_workspace()
    os.makedirs(output_dir, exist_ok=True)
    filename = f"imf_{args.dataset}_{args.indicator}_{args.country}_{args.start}_{args.end}.csv"
    filepath = os.path.join(output_dir, filename)

    try:
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
    except Exception as e:
        print(json.dumps({"error": f"CSV 保存失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    summary = {
        "source": f"IMF {args.dataset}",
        "indicator": args.indicator,
        "country": args.country,
        "rows": len(df),
        "columns": list(df.columns),
        "csv_path": f"/workspace/data/{filename}",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
