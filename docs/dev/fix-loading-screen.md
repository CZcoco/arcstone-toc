# Loading 窗口白屏修复方案

## 问题

打包后启动，loading 窗口的 `data:text/html` URL 没有正常渲染，显示为白屏，持续约 5 秒直到主窗口出现。

## 原因

Electron 打包后对 `data:` URL 的支持不稳定，内联 HTML 可能无法渲染。

## 修复方案

### 1. 创建独立 loading HTML 文件

新建 `frontend/electron/loading.html`，深色背景 + ARCSTONE 标题 + spinner 动画。

### 2. 修改 main.cjs 的 createLoadingWindow()

```diff
- const html = `data:text/html;charset=utf-8,...`;
- loadingWin.loadURL(html);
+ loadingWin.loadFile(path.join(__dirname, "loading.html"));
```

### 3. 主窗口加 backgroundColor 防闪白

```diff
 const win = new BrowserWindow({
   width: 1200,
   height: 800,
+  backgroundColor: "#1a1a1a",  // 和应用主题色一致
   show: false,
```

### 4. 确保 loading.html 被打包

`frontend/package.json` 的 `files` 已包含 `electron/**/*`，所以 `electron/loading.html` 会自动打包，无需额外配置。

## 涉及文件

| 文件 | 改动 |
|------|------|
| `frontend/electron/loading.html` | 新建：深色启动画面 |
| `frontend/electron/main.cjs` | `createLoadingWindow()` 改用 `loadFile`；`createWindow()` 加 `backgroundColor` |
