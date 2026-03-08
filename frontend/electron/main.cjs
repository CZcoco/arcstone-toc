const { app, BrowserWindow, dialog } = require("electron");
const { spawn, execSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

app.setName("econ-agent");
const API_HOST = "127.0.0.1";
const API_PORT = Number(process.env.ECON_AGENT_API_PORT || 18081);

let pyProcess = null;
let loadingWin = null;

function getPythonPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "python", "python.exe");
  }
  return "D:/miniconda/envs/miner-agent/python.exe";
}

function getProjectRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "app");
  }
  return path.join(__dirname, "../..");
}

/** 用户数据目录：%APPDATA%/econ-agent */
function getUserDataDir() {
  return app.getPath("userData"); // %APPDATA%/econ-agent
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

function startPython() {
  const pythonPath = getPythonPath();
  const projectRoot = getProjectRoot();
  pyProcess = spawn(pythonPath, ["run_api.py"], {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHON_EXECUTABLE: pythonPath,
      PYTHONUTF8: "1",
      ECON_AGENT_USER_DATA: getUserDataDir(),
      ECON_AGENT_API_PORT: String(API_PORT),
    },
    windowsHide: true,
  });
  pyProcess.stdout.on("data", (d) => console.log("[py]", d.toString()));
  pyProcess.stderr.on("data", (d) => console.error("[py]", d.toString()));
  pyProcess.on("exit", (code) => console.log("[py] exited", code));
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
      http.get(`http://${API_HOST}:${API_PORT}/api/health`, (res) => {
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
    title: "econ-agent",
    show: false,
    backgroundColor: "#f5f3ef",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (!app.isPackaged) {
    win.loadURL("http://localhost:5173");
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  win.once("ready-to-show", () => {
    if (loadingWin) { loadingWin.close(); loadingWin = null; }
    win.show();
  });
}

app.whenReady().then(async () => {
  ensureDataDir();
  createLoadingWindow();
  startPython();
  try {
    await waitForBackend(60);
  } catch {
    if (loadingWin) { loadingWin.close(); loadingWin = null; }
    dialog.showErrorBox("启动失败", "后端服务未能启动，请检查 Python 环境是否完整");
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
