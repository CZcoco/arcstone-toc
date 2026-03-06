---
name: data
description: 经济数据获取工具集，支持国家统计局、World Bank、FRED、IMF、UN Comtrade 五个公开数据源，自动下载并保存为 CSV 文件。
---

# 数据获取 Skill

## 支持的数据源

| 脚本 | 数据源 | 覆盖内容 | 是否需要 Key |
|------|--------|----------|-------------|
| `get_stats_cn.py` | 国家统计局（NBS） | 中国宏观经济指标 | 否 |
| `get_world_bank.py` | World Bank | 全球发展指标 | 否 |
| `get_fred.py` | FRED（美联储） | 美国及全球宏观数据 | 是（FRED_API_KEY） |
| `get_imf.py` | IMF | 国际货币基金数据 | 否 |
| `get_comtrade.py` | UN Comtrade | 国际贸易数据 | 否（有频率限制）|

## 调用方法

所有脚本通过 `run_python` 调用 subprocess 执行：

```python
import subprocess, sys, json

# World Bank：中国 GDP 数据（2000-2023）
result = subprocess.run(
    [sys.executable, "/skills/data/scripts/get_world_bank.py",
     "--indicator", "NY.GDP.MKTP.CD",
     "--countries", "CN",
     "--start", "2000", "--end", "2023"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout)  # 输出摘要 + CSV 路径
if result.returncode != 0:
    print("ERROR:", result.stderr)
```

```python
# 国家统计局：GDP 数据
result = subprocess.run(
    [sys.executable, "/skills/data/scripts/get_stats_cn.py",
     "--indicator", "A010101",
     "--start", "2010", "--end", "2023"],
    capture_output=True, text=True, timeout=60
)
```

```python
# FRED：美国 CPI（需要 FRED_API_KEY 环境变量）
result = subprocess.run(
    [sys.executable, "/skills/data/scripts/get_fred.py",
     "--series", "CPIAUCSL",
     "--start", "2010", "--end", "2023"],
    capture_output=True, text=True, timeout=60
)
```

```python
# IMF：中国实际 GDP 增速
result = subprocess.run(
    [sys.executable, "/skills/data/scripts/get_imf.py",
     "--dataset", "IFS",
     "--indicator", "NGDP_RPCH",
     "--country", "CN"],
    capture_output=True, text=True, timeout=60
)
```

```python
# UN Comtrade：中美贸易（156=中国, 842=美国, 2023年）
result = subprocess.run(
    [sys.executable, "/skills/data/scripts/get_comtrade.py",
     "--reporter", "156",
     "--partner", "842",
     "--year", "2023"],
    capture_output=True, text=True, timeout=60
)
```

## 输出说明

- CSV 文件保存到 `/workspace/data/{来源}_{指标}_{时间范围}.csv`
- stdout 返回摘要：行数、列名、文件路径
- 文件保存后，用 `run_python` 读取 CSV 进行进一步处理

## 付费数据库（CSMAR/WIND/CNKI）

这些数据库无法自动获取，需要用户手动操作：
1. 用户自行登录数据库网站下载 CSV/Excel
2. 通过前端上传功能上传到工作区
3. Agent 用 `run_python` 读取处理

**提示用户时说明**：
- CSMAR（国泰安）：适合中国A股上市公司财务数据
- WIND：适合金融市场高频数据
- CNKI：适合省级面板数据（各省统计年鉴整合版）

## 常用 World Bank 指标代码

| 代码 | 含义 |
|------|------|
| `NY.GDP.MKTP.CD` | GDP（当前美元） |
| `NY.GDP.PCAP.CD` | 人均 GDP |
| `SL.UEM.TOTL.ZS` | 失业率 |
| `SP.POP.TOTL` | 总人口 |
| `NE.TRD.GNFS.ZS` | 贸易占 GDP 比重 |
| `IT.NET.USER.ZS` | 互联网用户占比 |
| `SE.XPD.TOTL.GD.ZS` | 教育支出占 GDP |
| `SH.XPD.CHEX.GD.ZS` | 卫生支出占 GDP |

## 常用 FRED 序列代码

| 代码 | 含义 |
|------|------|
| `CPIAUCSL` | 美国 CPI |
| `UNRATE` | 美国失业率 |
| `GDP` | 美国实际 GDP |
| `FEDFUNDS` | 联邦基金利率 |
