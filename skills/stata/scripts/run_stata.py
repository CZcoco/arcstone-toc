"""
run_stata.py - Standalone PyStata executor
自动检测 Stata 安装路径，自动安装依赖。

Usage:
    python run_stata.py <do_file>
    python run_stata.py -c "command1" "command2"
    python run_stata.py --setup          # 仅安装依赖+检测 Stata
"""

import sys
import os
import json
import tempfile
import argparse
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "stata_config.json")

# ─── Auto-detect Stata ──────────────────────────────────────────────────

WINDOWS_CANDIDATES = [
    "C:/Program Files/Stata19", "D:/Program Files/Stata19",
    "C:/Program Files/Stata18", "D:/Program Files/Stata18",
    "C:/Program Files/Stata17", "D:/Program Files/Stata17",
    "C:/Stata19", "D:/Stata19", "C:/Stata18", "D:/Stata18",
    "C:/Stata17", "D:/Stata17",
]
MAC_CANDIDATES = [
    "/Applications/Stata", "/Applications/Stata19",
    "/Applications/Stata18", "/Applications/Stata17",
]
LINUX_CANDIDATES = [
    "/usr/local/stata19", "/usr/local/stata18",
    "/usr/local/stata17", "/usr/local/stata",
]

def _detect_stata():
    """Auto-detect Stata path and edition. Returns (path, edition) or (None, None)."""
    system = platform.system()
    if system == "Windows":
        candidates = WINDOWS_CANDIDATES
    elif system == "Darwin":
        candidates = MAC_CANDIDATES
    else:
        candidates = LINUX_CANDIDATES

    for d in candidates:
        pystata = os.path.join(d, "utilities", "pystata")
        if os.path.isdir(pystata):
            for ed in ["mp", "se", "be"]:
                if system == "Windows":
                    exe = os.path.join(d, f"Stata{ed.upper()}-64.exe")
                else:
                    exe = os.path.join(d, f"stata-{ed}")
                if os.path.exists(exe):
                    return d.replace("\\", "/"), ed
            return d.replace("\\", "/"), "mp"
    return None, None

def _load_or_detect_config():
    """Load config from file, or auto-detect and save."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)

    path, edition = _detect_stata()
    if path is None:
        print("[Error] Stata not found. Create stata_config.json manually:", file=sys.stderr)
        print(f'  {{"stata_path": "/path/to/Stata18", "stata_edition": "mp"}}', file=sys.stderr)
        print(f"  Save to: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    config = {"stata_path": path, "stata_edition": edition}
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)
    print(f"[Auto-detected] Stata at {path} (edition: {edition})", file=sys.stderr)
    print(f"[Saved] {CONFIG_PATH}", file=sys.stderr)
    return config

# ─── Dependency check ────────────────────────────────────────────────────

def _ensure_stata_setup():
    """Install stata_setup if not available."""
    try:
        import stata_setup
    except ImportError:
        import subprocess
        print("[Installing] stata_setup ...", file=sys.stderr)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "stata_setup", "-q"],
            stdout=subprocess.DEVNULL,
        )
        print("[Installed] stata_setup", file=sys.stderr)

# ─── PyStata init ────────────────────────────────────────────────────────

def _init_stata(config):
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    try:
        import stata_setup
        stata_setup.config(config["stata_path"], config["stata_edition"])
    finally:
        sys.stdout.close()
        sys.stdout = old_stdout

    from pystata import stata, config as pycfg
    pycfg.stoutputf = open(os.devnull, 'w', encoding='utf-8')
    return stata

# ─── Execution ───────────────────────────────────────────────────────────

def run_code(stata, code, working_dir=None):
    tmp_dir = tempfile.gettempdir()
    log_fd, log_path = tempfile.mkstemp(suffix='.log', prefix='stata_', dir=tmp_dir)
    os.close(log_fd)
    log_fwd = log_path.replace('\\', '/')

    wrapped = 'capture log close _all\n'
    wrapped += f'log using "{log_fwd}", replace text\n'
    if working_dir:
        wrapped += f'cd "{working_dir.replace(chr(92), "/")}"\n'
    wrapped += code + '\n'
    wrapped += 'capture log close _all\n'

    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    try:
        stata.run(wrapped, echo=True, quietly=False)
    except Exception:
        pass
    finally:
        sys.stdout.close()
        sys.stdout = old_stdout

    output = ""
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            output = f.read()
    except FileNotFoundError:
        output = "[Error: No log output captured]"
    finally:
        try:
            os.unlink(log_path)
        except OSError:
            pass

    # Clean log header/footer
    lines = output.splitlines()
    cleaned = []
    in_header = True
    for line in lines:
        s = line.strip()
        if in_header:
            if s.startswith('---') or s.startswith('name:') \
               or 'log:' in s or 'log type:' in s \
               or 'opened on:' in s or s == '':
                continue
            if s.startswith('. capture log close') or s.startswith('. log using'):
                continue
            if s.startswith('. cd "'):
                continue
            in_header = False
        if s.startswith('. capture log close'):
            continue
        if not in_header:
            cleaned.append(line)
    return '\n'.join(cleaned).strip()

def run_do_file(stata, filepath, working_dir=None):
    filepath = os.path.abspath(filepath)
    if not os.path.exists(filepath):
        return f"[Error: File not found: {filepath}]"
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        code = f.read()
    if working_dir is None:
        working_dir = os.path.dirname(filepath)
    return run_code(stata, code, working_dir)

# ─── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Execute Stata code via PyStata')
    parser.add_argument('dofile', nargs='?', help='Path to .do file')
    parser.add_argument('-c', '--command', nargs='+', help='Inline Stata command(s)')
    parser.add_argument('-w', '--working-dir', help='Working directory')
    parser.add_argument('--setup', action='store_true', help='Only install deps and detect Stata')
    args = parser.parse_args()

    # Always ensure deps + config
    _ensure_stata_setup()
    config = _load_or_detect_config()

    if args.setup:
        # Verify PyStata works
        try:
            stata = _init_stata(config)
            print(f"[OK] Stata {config['stata_edition'].upper()} at {config['stata_path']}")
            print(f"[OK] PyStata initialized successfully")
            print(f"[OK] Config: {CONFIG_PATH}")
        except Exception as e:
            print(f"[Error] PyStata init failed: {e}")
            sys.exit(1)
        return

    if not args.dofile and not args.command:
        parser.print_help()
        sys.exit(1)

    stata = _init_stata(config)

    if args.command:
        code = '\n'.join(args.command)
        output = run_code(stata, code, args.working_dir)
    else:
        output = run_do_file(stata, args.dofile, args.working_dir)

    print(output)

if __name__ == '__main__':
    main()
