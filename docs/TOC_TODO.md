# ToC 待办事项

> 记录当前所有未完成的服务端部署和配置工作。代码已写好但需要实际操作的事项。

---

## 1. VPS Key 池配置

**状态**：代码已完成，等待 VPS 配置

客户端启动时会从 `{NEW_API_URL}/config/keys.json` 拉取 Tavily 和 MinerU 的 API key 列表。

**需要做的**：

1. 在 VPS 上创建静态 JSON 文件，让 Caddy 能 serve 它：
   ```bash
   # 在 VPS 上
   mkdir -p /srv/config
   cat > /srv/config/keys.json << 'EOF'
   {
     "tavily": [
       "tvly-xxxxxx",
       "tvly-yyyyyy"
     ],
     "mineru": [
       "mineru-xxxxxx"
     ]
   }
   EOF
   ```

2. Caddy 配置加一条静态文件路由：
   ```
   handle /config/* {
       root * /srv
       file_server
   }
   ```

3. 获取多个 Tavily key：去 [tavily.com](https://tavily.com) 注册多个账号，每个免费 1000 次/月
4. 获取 MinerU key：去 [mineru.net](https://mineru.net) 获取 API key

**相关代码**：`src/api/key_pool.py`，启动加载在 `src/api/app.py`

---

## 2. RAG 代理部署

**状态**：客户端代码已改为 HTTP 请求服务端代理，但服务端 RAG 代理未部署

客户端知识库检索已改为请求 `RAG_PROXY_URL`（默认 `http://43.128.44.82:3000/rag/retrieve`），但 VPS 上还没有跑 RAG 代理容器。

**需要做的**：

1. 在 VPS 上部署 `rag-proxy` Docker 容器（代码在 `rag-proxy/` 目录）
2. 配置百炼 AK/SK 作为容器环境变量
3. Caddy 配置加路由：
   ```
   handle /rag/* {
       reverse_proxy rag-proxy:8100
   }
   ```
4. 测试：从客户端发起知识库检索，验证能返回结果

**相关代码**：`src/tools/rag.py`（客户端端），`rag-proxy/`（服务端）

**负责人**：室友

---

## 3. 支付系统接入

**状态**：客户端充值弹窗已完成，等待支付平台配置

Electron 充值弹窗（Phase 2.5）代码已完成：点"充值"→ 弹出 New API 的 /topup 页面 → 关闭后自动刷新余额。但 New API 后台的支付设置还没配。

**需要做的**：

1. **获取营业执照**：办个体工商户（或借一个），用于申请支付宝当面付
2. **申请支付宝当面付**：在 [open.alipay.com](https://open.alipay.com) 申请，费率 0.6%
3. **部署易支付网关**（可选）：如果用支付宝当面付，需要一个 EPay 兼容的支付网关（如 [彩虹易支付](https://github.com/lopinx/epay)）来桥接 New API
4. **New API 后台配置**：运营设置 → 支付设置 → 填入 EPay API 地址、商户 PID、商户 KEY
5. **设置充值比例**：多少 CNY = 多少 tokens
6. **Caddy HTTPS**：确保支付回调 URL 走 HTTPS（EPay 回调要求）
7. **注意**：New API 已知 bug #900 — 支付回调路径 `/api/user/epay/notify` 必须被 Caddy 正确代理

**备选方案**（无执照时）：虎皮椒(xunhupay.com)，个人可注册，费率 1.5-2%，但需要适配器

**相关代码**：
- Electron 弹窗：`frontend/electron/main.cjs`（IPC handler）、`frontend/src/hooks/useTopup.ts`
- 后端 context：`src/api/routes.py`（`/auth/topup-context`）

---

## 4. HTTPS + 域名

**状态**：未开始

目前 New API 跑在 `http://43.128.44.82:3000`（裸 IP + HTTP）。生产环境需要：

1. 注册一个域名（如 `api.econ-agent.com`）
2. 配置 DNS 指向 VPS IP
3. Caddy 自动签发 HTTPS 证书
4. 客户端 `NEW_API_URL` 改为 `https://api.econ-agent.com/v1`

**为什么重要**：支付回调要求 HTTPS；用户看到 IP 地址不专业；浏览器对 HTTP 有安全警告。

---

## 5. 设置页隐藏后的遗留

**状态**：已完成，需注意

设置页已从 UI 隐藏（ToC 用户不需要配任何 key）。但后端 API 路由（`/settings/schema`、`/settings`、`PUT /settings`）仍保留，未来如果需要高级设置可以恢复。

`SETTINGS_SCHEMA` 目前仍有 `NEW_API_URL` 和 `TAVILY_API_KEY` 两个字段定义，只是前端不再展示。

---

## 优先级排序

| 优先级 | 事项 | 阻塞情况 |
|--------|------|----------|
| **P0** | Key 池配置 | 没有 key 就无法搜索和解析 PDF |
| **P0** | HTTPS + 域名 | 支付回调和安全性都需要 |
| **P1** | 支付系统 | 没支付就不能收费，但不阻塞功能使用 |
| **P1** | RAG 代理 | 知识库功能不可用，但不阻塞核心对话 |
| **P2** | Phase 3 UX | 新手引导、模板卡片、品牌更新 |
