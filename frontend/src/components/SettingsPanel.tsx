import { useState, useEffect, useCallback } from "react";
import { X, Save, Loader2, Eye, EyeOff } from "lucide-react";
import {
  getSettingsSchema, getSettings, updateSettings,
} from "@/lib/api";
import type { SettingsGroup } from "@/lib/api";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
  onSaved?: (changedKeys: string[]) => void | Promise<void>;
}

export default function SettingsPanel({ open, onClose, onSaved }: SettingsPanelProps) {
  const [schema, setSchema] = useState<SettingsGroup[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "ok" | "error" } | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [schemaRes, settingsRes] = await Promise.all([
        getSettingsSchema(),
        getSettings(),
      ]);
      setSchema(schemaRes.schema);
      setValues(settingsRes.settings);
      setDraft(settingsRes.settings);
      setVisibleKeys(new Set());
      setMessage(null);
    } catch {
      setMessage({ text: "加载设置失败", type: "error" });
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  const hasChanges = JSON.stringify(draft) !== JSON.stringify(values);

  function handleChange(key: string, value: string) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  function toggleVisible(key: string) {
    setVisibleKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const result = await updateSettings(draft);
      if (result.changed_keys.length > 0) {
        setMessage({ text: "已保存", type: "ok" });
      } else {
        setMessage({ text: "无变更", type: "ok" });
      }
      // 重新加载以获取最新脱敏值
      const settingsRes = await getSettings();
      setValues(settingsRes.settings);
      setDraft(settingsRes.settings);
      setVisibleKeys(new Set());
      if (result.changed_keys.length > 0) {
        await onSaved?.(result.changed_keys);
      }
    } catch {
      setMessage({ text: "保存失败", type: "error" });
    }
    setSaving(false);
  }

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 z-40 animate-fade-in"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-[720px] max-w-full bg-white z-50 shadow-2xl
                      flex flex-col animate-slide-left">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-sand-200/60">
          <h2 className="text-[0.9375rem] font-semibold text-sand-800">设置</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-100 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={20} className="animate-spin text-sand-400" />
            </div>
          ) : (
            schema.map((group) => (
              <div key={group.group} className="rounded-xl border border-sand-200/60 bg-sand-50/50">
                {/* Group header */}
                <div className="flex items-center gap-2 px-4 py-3 border-b border-sand-200/40">
                  <span className="text-[0.8125rem] font-medium text-sand-700">
                    {group.group}
                  </span>
                </div>

                {/* Fields */}
                <div className="px-4 py-3 space-y-3">
                  {group.keys.map((keyDef) => {
                    const val = draft[keyDef.key] ?? "";
                    const isSensitive = keyDef.sensitive;
                    const isVisible = visibleKeys.has(keyDef.key);

                    return (
                      <div key={keyDef.key}>
                        <label className="block text-[0.75rem] text-sand-500 mb-1">
                          {keyDef.label}
                          <span className="ml-1.5 text-[0.6875rem] text-sand-400 font-mono">
                            {keyDef.key}
                          </span>
                        </label>
                        <div className="relative">
                          <input
                            type={isSensitive && !isVisible ? "password" : "text"}
                            value={val}
                            onChange={(e) => handleChange(keyDef.key, e.target.value)}
                            placeholder="未设置"
                            className="w-full px-3 py-2 text-[0.8125rem] rounded-lg border border-sand-200
                                       bg-white text-sand-800 placeholder:text-sand-300
                                       focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20
                                       transition-colors font-mono pr-9"
                          />
                          {isSensitive && (
                            <button
                              type="button"
                              onClick={() => toggleVisible(keyDef.key)}
                              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-sand-400
                                         hover:text-sand-600 transition-colors"
                            >
                              {isVisible ? <EyeOff size={14} /> : <Eye size={14} />}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-sand-200/60 flex items-center gap-3">
          {message && (
            <div className={`flex items-center gap-1.5 text-[0.8125rem] ${
              message.type === "ok" ? "text-green-600" : "text-red-600"
            }`}>
              {message.text}
            </div>
          )}
          <div className="flex-1" />
          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            className="flex items-center gap-1.5 px-4 py-2 text-[0.8125rem] rounded-lg
                       bg-accent text-white hover:bg-accent/90
                       disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            保存
          </button>
        </div>
      </div>
    </>
  );
}
