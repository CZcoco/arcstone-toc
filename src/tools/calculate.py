"""
财务计算工具 - IRR / NPV / 投资回收期
"""
from langchain_core.tools import tool


@tool
def calculate_irr(
    initial_investment: float,
    annual_cashflows: list[float],
    discount_rate: float = 0.10,
) -> dict:
    """计算矿业项目的投资回报指标。

    参数：
        initial_investment: 初始投资额（正数，单位：万元）
        annual_cashflows: 各年净现金流列表（单位：万元）
        discount_rate: 折现率（默认 10%）

    返回：
        包含 IRR、NPV、投资回收期的字典

    示例：
        calculate_irr(10000, [2000, 2500, 3000, 3500, 4000])
    """
    # 构建完整现金流（第0年为负的初始投资）
    cashflows = [-initial_investment] + list(annual_cashflows)

    # 计算 NPV 的辅助函数
    def npv_at_rate(rate):
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))

    # 计算 IRR（二分法）
    lo, hi = -0.99, 10.0
    irr = None
    for _ in range(1000):
        mid = (lo + hi) / 2
        npv = npv_at_rate(mid)
        if abs(npv) < 1e-6:
            irr = mid
            break
        if npv > 0:
            lo = mid
        else:
            hi = mid
    if irr is None:
        irr = mid

    # 计算 NPV
    npv = npv_at_rate(discount_rate)

    # 计算投资回收期
    cumsum = 0.0
    payback_period = None
    for t, cf in enumerate(cashflows):
        cumsum += cf
        if cumsum >= 0 and payback_period is None:
            if t > 0:
                prev_cumsum = cumsum - cf
                payback_period = (t - 1 + (-prev_cumsum) / cf) if cf != 0 else float(t)
            else:
                payback_period = 0.0

    return {
        "IRR": f"{irr * 100:.2f}%",
        "NPV": f"{npv:,.0f} 万元",
        "投资回收期": f"{payback_period:.1f} 年" if payback_period is not None else "超出计算期限",
        "折现率": f"{discount_rate * 100:.0f}%",
        "总投资": f"{initial_investment:,.0f} 万元",
        "项目周期": f"{len(annual_cashflows)} 年",
    }
