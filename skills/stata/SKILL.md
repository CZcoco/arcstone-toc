---
name: stata
description: "Use this skill whenever the user wants to run Stata commands, execute .do files, or perform econometric/statistical analysis using Stata. This includes regression analysis, panel data models, IV estimation, diff-in-diff, RDD, summary statistics, data cleaning, and any task that requires Stata syntax. If the user mentions Stata, .do files, or asks for econometric analysis that Stata excels at, use this skill."
---

# Stata Execution Guide

## Setup (only once)

The script auto-installs dependencies and auto-detects Stata on first run. No manual setup needed in most cases.

If the first run fails with "Stata not found", ask the user for their Stata installation directory, then create config:

```python
import json
config = {"stata_path": "USER_PROVIDED_PATH", "stata_edition": "mp"}
with open("/skills/stata/scripts/stata_config.json", "w") as f:
    json.dump(config, f, indent=4)
```

To explicitly verify the setup, run:

```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, "/skills/stata/scripts/run_stata.py", "--setup"],
    capture_output=True, text=True, timeout=120
)
print(result.stdout)
```

## How to Run Stata Code

### Inline commands (short tasks)

```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, "/skills/stata/scripts/run_stata.py",
     "-c",
     "sysuse auto, clear",
     "reg price mpg weight, r"],
    capture_output=True, text=True, timeout=120
)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
```

### Run a .do file (longer scripts)

Write the .do file first, then execute:

```python
import subprocess, sys

do_code = """
clear all
set more off
sysuse auto, clear
reg price mpg weight foreign, r
estat vif
"""

with open("/workspace/analysis.do", "w") as f:
    f.write(do_code)

result = subprocess.run(
    [sys.executable, "/skills/stata/scripts/run_stata.py",
     "/workspace/analysis.do"],
    capture_output=True, text=True, timeout=120
)
print(result.stdout)
```

### Specify working directory

```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, "/skills/stata/scripts/run_stata.py",
     "-w", "/workspace/data",
     "-c", "use survey_data, clear", "describe"],
    capture_output=True, text=True, timeout=120
)
print(result.stdout)
```

## Common Econometric Tasks

### OLS with robust SE
```
reg y x1 x2 x3, r
```

### Panel data (Fixed Effects / Random Effects)
```
xtset firm_id year
xtreg y x1 x2, fe r
xtreg y x1 x2, re r
hausman fe re
```

### IV / 2SLS
```
ivregress 2sls y x1 (x2 = z1 z2), r
estat firststage
estat overid
```

### Diff-in-Diff
```
reg y treat##post controls, r cluster(group_id)
```

### RDD
```
rdrobust y x, c(0) p(1)
```

### Export regression table (esttab pre-installed)
```
eststo clear
eststo: reg y x1, r
eststo: reg y x1 x2, r
eststo: reg y x1 x2 x3, r
esttab using "results.csv", replace se star(* 0.1 ** 0.05 *** 0.01) r2
```

### Summary statistics table
```
estpost summarize price mpg weight length
esttab using "sumstats.csv", replace cells("count mean sd min max") nomtitle nonumber
```

## Important Notes

- Each execution is independent — data and variables do NOT persist between calls
- Timeout: 120 seconds default, use longer timeout for large datasets
- Pre-installed packages: estout/esttab
- To install new Stata packages: download .ado/.sthlp files and place in the PLUS directory (ssc install is unavailable due to network issues)
- Graph export: `graph export "filename.png", replace`
- For multi-step analysis, prefer writing a .do file over many inline -c arguments
