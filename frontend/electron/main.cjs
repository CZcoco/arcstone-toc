const { app, BrowserWindow, dialog, session, Menu } = require("electron");
const { spawn, execSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

app.setName("Arcstone-econ");
const API_HOST = "127.0.0.1";
const DEFAULT_PORT = Number(process.env.ARCSTONE_ECON_API_PORT || 18081);
const PACKAGED_BACKEND_START_TIMEOUT_MS = 5 * 60 * 1000;
const PACKAGED_BACKEND_HEALTH_RETRIES = 5 * 60;

let pyProcess = null;
let loadingWin = null;
let actualPort = DEFAULT_PORT;

function getPythonPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "python", "python.exe");
  }
  const projectRoot = getProjectRoot();
  const venvPython = path.join(projectRoot, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  return process.env.PYTHON_EXECUTABLE || "python";
}

function getProjectRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "app");
  }
  return path.join(__dirname, "../..");
}

/** 用户数据目录：%APPDATA%/Arcstone-econ */
function getUserDataDir() {
  return app.getPath("userData");
}

/** Ensure required runtime data directories exist. */
function ensureDataDir() {
  const userDataDir = getUserDataDir();
  const dataDir = path.join(userDataDir, "data");
  const tmpDir = path.join(dataDir, "tmp");
  const workspaceDir = path.join(dataDir, "workspace");
  const skillsDir = path.join(dataDir, "skills");
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
  if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });
  if (!fs.existsSync(workspaceDir)) fs.mkdirSync(workspaceDir, { recursive: true });
  if (!fs.existsSync(skillsDir)) fs.mkdirSync(skillsDir, { recursive: true });
}

/** 覆盖安装兜底：杀掉可能残留的旧 backend.exe */
function killOldBackend() {
  if (!app.isPackaged) return;
  try {
    execSync("taskkill /f /im backend.exe", { windowsHide: true, stdio: "ignore" });
  } catch {
    // 没有旧进程，正常
  }
}

/**
 * 启动 Python 后端，返回 Promise<number>（实际端口）。
 * 打包模式传 port=0 让 OS 分配空闲端口；开发模式用固定端口。
 */
function startPython() {
  return new Promise((resolve, reject) => {
    const projectRoot = getProjectRoot();
    const envPort = app.isPackaged ? "0" : String(DEFAULT_PORT);

    if (app.isPackaged) {
      const backendExe = path.join(process.resourcesPath, "backend", "backend.exe");
      pyProcess = spawn(backendExe, [], {
        cwd: projectRoot,
        env: {
          ...process.env,
          PYTHON_EXECUTABLE: getPythonPath(),
          PYTHONUTF8: "1",
          PYTHONUNBUFFERED: "1",
          ARCSTONE_ECON_USER_DATA: getUserDataDir(),
          ARCSTONE_ECON_API_PORT: envPort,
          ARCSTONE_ECON_INSTALL_ROOT: projectRoot,
        },
        windowsHide: true,
      });
    } else {
      const pythonPath = getPythonPath();
      pyProcess = spawn(pythonPath, ["run_api.py"], {
        cwd: projectRoot,
        env: {
          ...process.env,
          PYTHON_EXECUTABLE: pythonPath,
          PYTHONUTF8: "1",
          PYTHONUNBUFFERED: "1",
          ARCSTONE_ECON_USER_DATA: getUserDataDir(),
          ARCSTONE_ECON_API_PORT: envPort,
        },
        windowsHide: true,
      });
    }

    let portResolved = false;

    pyProcess.stdout.on("data", (d) => {
      const text = d.toString();
      console.log("[py]", text);
      if (!portResolved) {
        const match = text.match(/ARCSTONE_PORT=(\d+)/);
        if (match) {
          actualPort = parseInt(match[1], 10);
          portResolved = true;
          resolve(actualPort);
        }
      }
    });

    pyProcess.stderr.on("data", (d) => console.error("[py]", d.toString()));

    pyProcess.on("exit", (code) => {
      console.log("[py] exited", code);
      if (!portResolved) reject(new Error(`Backend exited (code ${code}) before reporting port`));
    });

    setTimeout(() => {
      if (!portResolved) reject(new Error("Timeout waiting for backend port"));
    }, app.isPackaged ? PACKAGED_BACKEND_START_TIMEOUT_MS : 30000);
  });
}

/** Windows 下杀掉整个进程树，避免残留 */
function killPython() {
  if (!pyProcess) return;
  try {
    if (process.platform === "win32") {
      execSync(`taskkill /T /F /PID ${pyProcess.pid}`, { windowsHide: true, stdio: "ignore" });
    } else {
      pyProcess.kill();
    }
  } catch {
    // 进程可能已退出
  }
  pyProcess = null;
}

function waitForBackend(maxRetries = 60) {
  return new Promise((resolve, reject) => {
    let count = 0;
    const check = () => {
      http.get(`http://${API_HOST}:${actualPort}/api/health`, (res) => {
        if (res.statusCode === 200) resolve();
        else retry();
      }).on("error", retry);
    };
    function retry() {
      if (++count >= maxRetries) reject(new Error("Backend timeout"));
      else setTimeout(check, 1000);
    }
    check();
  });
}

/** 启动时显示 loading 窗口 */
function createLoadingWindow() {
  loadingWin = new BrowserWindow({
    width: 360,
    height: 200,
    frame: false,
    resizable: false,
    transparent: false,
    alwaysOnTop: true,
    backgroundColor: "#f5f3ef",
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });
  loadingWin.loadFile(path.join(__dirname, "loading.html"));
  loadingWin.on("closed", () => { loadingWin = null; });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: "Arcstone-econ",
    show: false,
    backgroundColor: "#f5f3ef",
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // 隐藏菜单栏
  win.removeMenu();
  Menu.setApplicationMenu(null);

  if (!app.isPackaged) {
    win.loadURL("http://localhost:5173");
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"), {
      query: { __port: String(actualPort) },
    });
  }

  win.once("ready-to-show", () => {
    if (loadingWin) { loadingWin.close(); loadingWin = null; }
    win.show();
  });
}

app.whenReady().then(async () => {
  // 代理绕过：让渲染进程对 localhost 的 fetch/SSE 不走系统代理
  await session.defaultSession.setProxy({
    proxyBypassRules: "127.0.0.1,localhost",
  });

  ensureDataDir();
  killOldBackend();
  createLoadingWindow();

  try {
    await startPython();
    await waitForBackend(app.isPackaged ? PACKAGED_BACKEND_HEALTH_RETRIES : 60);
  } catch (e) {
    if (loadingWin) { loadingWin.close(); loadingWin = null; }
    const extraHint = app.isPackaged
      ? "\n\n首次启动可能正在联网安装 Python 依赖，请确认网络可用后稍候重试。"
      : "";
    dialog.showErrorBox("启动失败", `后端服务未能启动：${e.message}${extraHint}`);
    app.quit();
    return;
  }
  createWindow();
});

app.on("before-quit", () => {
  killPython();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
