import type { Session, MemoryItem, KBDocument, KBConfig } from "@/types";

export interface ModelInfo {
  id: string;
  name: string;
  model: string;
  available: boolean;
}

export const BASE_URL = window.location.protocol === "file:"
  ? "http://127.0.0.1:8000/api"
  : "/api";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export function createSession() {
  return request<{ thread_id: string }>(`${BASE_URL}/session/new`, { method: "POST" });
}

export function listSessions() {
  return request<{ sessions: Session[] }>(`${BASE_URL}/session/list`);
}

export function getSessionHistory(threadId: string) {
  return request<{ messages: Array<{ role: string; content: string; tool_calls?: any[]; name?: string; tool_call_id?: string }> }>(
    `${BASE_URL}/session/${threadId}`
  );
}

export function listMemory() {
  return request<{ items: MemoryItem[] }>(`${BASE_URL}/memory/list`);
}

export function getMemory(key: string) {
  const k = key.startsWith("/") ? key.slice(1) : key;
  return request<{ key: string; content: string }>(`${BASE_URL}/memory/${k}`);
}

export function healthCheck() {
  return request<{ status: string }>(`${BASE_URL}/health`);
}

export function renameSession(threadId: string, title: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/session/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, title }),
  });
}

export function deleteSession(threadId: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/session/${threadId}`, {
    method: "DELETE",
  });
}

export function archiveSession(threadId: string) {
  return fetch(`${BASE_URL}/archive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId }),
  });
}

export function cancelChat(threadId: string) {
  return request<{ cancelled: boolean }>(`${BASE_URL}/chat/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId }),
  });
}

export function listModels() {
  return request<{ models: ModelInfo[] }>(`${BASE_URL}/models`);
}

export function uploadPdf(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ ok: boolean; path?: string; pages?: number; chars?: number; method?: string; error?: string }>(
    `${BASE_URL}/upload/pdf`,
    { method: "POST", body: form }
  );
}

export function uploadPdfs(files: File[]) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  return request<{
    results: Array<{
      ok: boolean; name: string;
      path?: string; pages?: number; chars?: number; method?: string; error?: string;
    }>;
  }>(`${BASE_URL}/upload/pdfs`, { method: "POST", body: form });
}

export function uploadImage(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ ok: boolean; image_id?: string; name?: string; error?: string }>(
    `${BASE_URL}/upload/image`,
    { method: "POST", body: form }
  );
}

export function uploadExcel(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ ok: boolean; name?: string; path?: string; error?: string }>(
    `${BASE_URL}/upload/excel`,
    { method: "POST", body: form }
  );
}

export function updateMemory(key: string, content: string) {
  const k = key.startsWith("/") ? key.slice(1) : key;
  return request<{ ok: boolean }>(`${BASE_URL}/memory/${k}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export function deleteMemory(key: string) {
  const k = key.startsWith("/") ? key.slice(1) : key;
  return request<{ ok: boolean }>(`${BASE_URL}/memory/${k}`, {
    method: "DELETE",
  });
}

export function renameMemory(oldKey: string, newName: string) {
  return request<{ ok: boolean; new_key?: string; error?: string }>(`${BASE_URL}/memory/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ old_key: oldKey, new_name: newName }),
  });
}

// --- Knowledge Base (百炼) ---

export function listKBDocuments(page = 1, pageSize = 20, indexId?: string) {
  let url = `${BASE_URL}/kb/list?page=${page}&page_size=${pageSize}`;
  if (indexId) url += `&index_id=${encodeURIComponent(indexId)}`;
  return request<{ documents: KBDocument[]; total_count: number }>(url);
}

export function uploadToKB(file: File, indexId?: string, chunkSize?: number, overlapSize?: number) {
  const form = new FormData();
  form.append("file", file);
  if (indexId) form.append("index_id", indexId);
  if (chunkSize != null) form.append("chunk_size", String(chunkSize));
  if (overlapSize != null) form.append("overlap_size", String(overlapSize));
  return request<{ job_id: string; filename: string; status: string }>(
    `${BASE_URL}/kb/upload`,
    { method: "POST", body: form }
  );
}

export function getKBUploadStatus(jobId: string) {
  return request<{
    job_id: string; filename: string; status: string;
    progress: string; error: string | null; file_id: string | null;
  }>(`${BASE_URL}/kb/upload/status?job_id=${jobId}`);
}

export function deleteKBDocuments(documentIds: string[], indexId?: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/kb/delete`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds, index_id: indexId || null }),
  });
}

export function getKBRagConfig() {
  return request<{ configs: KBConfig[] }>(`${BASE_URL}/kb/rag/config`);
}

export function setKBRagConfig(configs: KBConfig[]) {
  return request<{ ok: boolean }>(`${BASE_URL}/kb/rag/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ configs }),
  });
}

// --- System Prompt ---

export interface PromptVersion {
  id: string;
  name: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export function getSystemPrompt() {
  return request<{ content: string; is_default: boolean }>(`${BASE_URL}/system-prompt`);
}

export function updateSystemPrompt(content: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/system-prompt`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export function listPromptVersions() {
  return request<{ versions: PromptVersion[]; active_id: string | null }>(`${BASE_URL}/system-prompt/versions`);
}

export function createPromptVersion(name: string, content = "") {
  return request<{ ok: boolean; version: PromptVersion }>(`${BASE_URL}/system-prompt/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, content }),
  });
}

export function updatePromptVersion(id: string, data: { name?: string; content?: string }) {
  return request<{ ok: boolean; version: PromptVersion }>(`${BASE_URL}/system-prompt/versions/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function deletePromptVersion(id: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/system-prompt/versions/${id}`, {
    method: "DELETE",
  });
}

export function activatePromptVersion(id: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/system-prompt/activate/${id}`, {
    method: "POST",
  });
}

// --- Settings ---

export interface SettingsKeyDef {
  key: string;
  label: string;
  sensitive: boolean;
}

export interface SettingsGroup {
  group: string;
  needs_restart?: boolean;
  keys: SettingsKeyDef[];
}

export function getSettingsSchema() {
  return request<{ schema: SettingsGroup[] }>(`${BASE_URL}/settings/schema`);
}

export function getSettings() {
  return request<{ settings: Record<string, string> }>(`${BASE_URL}/settings`);
}

export function updateSettings(settings: Record<string, string>) {
  return request<{ ok: boolean; changed_keys: string[] }>(
    `${BASE_URL}/settings`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    }
  );
}

// --- Skills ---

export interface SkillSummary {
  name: string;
  dir_name: string;
  description: string;
}

export interface SkillDetail {
  dir_name: string;
  name: string;
  description: string;
  raw: string;
}

export function listSkills() {
  return request<{ skills: SkillSummary[] }>(`${BASE_URL}/skills`);
}

export function getSkill(dirName: string) {
  return request<SkillDetail>(`${BASE_URL}/skills/${encodeURIComponent(dirName)}`);
}

export function updateSkill(dirName: string, name: string, description: string, content: string) {
  return request<{ ok: boolean; dir_name: string }>(`${BASE_URL}/skills/${encodeURIComponent(dirName)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, content }),
  });
}

export function deleteSkill(dirName: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/skills/${encodeURIComponent(dirName)}`, {
    method: "DELETE",
  });
}

export interface SkillFile {
  path: string;
  size: number;
}

export function listSkillFiles(dirName: string) {
  return request<{ files: SkillFile[] }>(`${BASE_URL}/skills/${encodeURIComponent(dirName)}/files`);
}

export function readSkillFile(dirName: string, filePath: string) {
  return request<{ path: string; content: string; binary?: boolean }>(
    `${BASE_URL}/skills/${encodeURIComponent(dirName)}/files/${filePath}`
  );
}

export function writeSkillFile(dirName: string, filePath: string, content: string) {
  return request<{ ok: boolean }>(
    `${BASE_URL}/skills/${encodeURIComponent(dirName)}/files/${filePath}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }
  );
}

export function deleteSkillFile(dirName: string, filePath: string) {
  return request<{ ok: boolean }>(
    `${BASE_URL}/skills/${encodeURIComponent(dirName)}/files/${filePath}`,
    { method: "DELETE" }
  );
}

// --- Workspace ---

export interface WorkspaceFile {
  path: string;
  size: number;
  modified: string;
}

export function getWorkspace() {
  return request<{ path: string; files: WorkspaceFile[] }>(`${BASE_URL}/workspace`);
}

export function setWorkspace(path: string) {
  return request<{ ok: boolean; path: string }>(`${BASE_URL}/workspace/set`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
}

export function readWorkspaceFile(filePath: string) {
  return request<{ path: string; content: string; binary?: boolean }>(
    `${BASE_URL}/workspace/file/${filePath.split("/").map(encodeURIComponent).join("/")}`
  );
}

export function deleteWorkspaceFile(filePath: string) {
  return request<{ ok: boolean }>(
    `${BASE_URL}/workspace/file/${filePath.split("/").map(encodeURIComponent).join("/")}`,
    { method: "DELETE" }
  );
}

export function pickWorkspaceFolder() {
  return request<{ path: string | null }>(`${BASE_URL}/workspace/pick`, {
    method: "POST",
  });
}

export function revealInExplorer(path?: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/workspace/reveal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: path ?? null }),
  });
}

export function workspaceRawUrl(filePath: string) {
  return `${BASE_URL}/workspace/raw/${filePath.split("/").map(encodeURIComponent).join("/")}`;
}
