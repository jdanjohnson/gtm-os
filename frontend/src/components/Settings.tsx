import { useCallback, useEffect, useState } from "react";
import { BrandIdentity, Integration, NoKeyTool, ToolKeyInfo, getBrand, getHealth, getIntegrations, getToolKeys, updateBrand, updateIntegrationKeys, updateToolKeys } from "../lib/api";

const SOCIAL_KEYS = ["twitter", "linkedin", "instagram", "youtube", "tiktok", "github"] as const;

const EMPTY_BRAND: BrandIdentity = {
  company_name: "",
  tagline: "",
  website: "",
  product_description: "",
  social: {},
  icp: "",
  icp_negative: "",
  voice: [],
  avoid: [],
  prefer: [],
  email_max_sentences: 4,
  email_max_words: 90,
};

export default function Settings() {
  const [health, setHealth] = useState<Awaited<ReturnType<typeof getHealth>> | null>(null);
  const [brand, setBrand] = useState<BrandIdentity>(EMPTY_BRAND);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [intKeyDrafts, setIntKeyDrafts] = useState<Record<string, string>>({});
  const [intSaving, setIntSaving] = useState(false);
  const [intSaved, setIntSaved] = useState(false);
  const [toolKeys, setToolKeys] = useState<ToolKeyInfo[]>([]);
  const [noKeyTools, setNoKeyTools] = useState<NoKeyTool[]>([]);
  const [toolKeyDrafts, setToolKeyDrafts] = useState<Record<string, string>>({});
  const [toolKeySaving, setToolKeySaving] = useState(false);
  const [toolKeySaved, setToolKeySaved] = useState(false);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => null);
    getBrand()
      .then((b) => setBrand(b))
      .catch(() => null);
    getIntegrations()
      .then((r) => setIntegrations(r.integrations))
      .catch(() => null);
    getToolKeys()
      .then((r) => {
        setToolKeys(r.tool_keys);
        setNoKeyTools(r.no_key_tools);
      })
      .catch(() => null);
  }, []);

  const update = useCallback(
    (patch: Partial<BrandIdentity>) => {
      setBrand((prev) => ({ ...prev, ...patch }));
      setDirty(true);
      setSaved(false);
    },
    [],
  );

  const updateSocial = useCallback(
    (key: string, value: string) => {
      setBrand((prev) => ({
        ...prev,
        social: { ...prev.social, [key]: value },
      }));
      setDirty(true);
      setSaved(false);
    },
    [],
  );

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const { brand_body: _, ...payload } = brand;
      const result = await updateBrand(payload);
      setBrand(result);
      setDirty(false);
      setSaved(true);
    } catch (e) {
      console.error("Failed to save brand:", e);
    } finally {
      setSaving(false);
    }
  }, [brand]);

  const saveIntegrationKeys = useCallback(async () => {
    setIntSaving(true);
    try {
      const payload: Record<string, string> = {};
      for (const [name, val] of Object.entries(intKeyDrafts)) {
        if (name === "composio") payload.composio_api_key = val;
        if (name === "pipedream") payload.pipedream_api_key = val;
      }
      await updateIntegrationKeys(payload);
      setIntKeyDrafts({});
      setIntSaved(true);
      // Refresh integrations and health status.
      const [intRes, hRes] = await Promise.all([getIntegrations(), getHealth()]);
      setIntegrations(intRes.integrations);
      setHealth(hRes);
    } catch (e) {
      console.error("Failed to save integration keys:", e);
    } finally {
      setIntSaving(false);
    }
  }, [intKeyDrafts]);

  const saveToolKeys = useCallback(async () => {
    setToolKeySaving(true);
    try {
      const payload: Record<string, string> = {};
      for (const [name, val] of Object.entries(toolKeyDrafts)) {
        if (name === "serper") payload.serper_api_key = val;
        if (name === "brave") payload.brave_search_api_key = val;
        if (name === "youtube") payload.youtube_api_key = val;
      }
      await updateToolKeys(payload);
      setToolKeyDrafts({});
      setToolKeySaved(true);
      const r = await getToolKeys();
      setToolKeys(r.tool_keys);
      setNoKeyTools(r.no_key_tools);
    } catch (e) {
      console.error("Failed to save tool keys:", e);
    } finally {
      setToolKeySaving(false);
    }
  }, [toolKeyDrafts]);

  const addListItem = useCallback(
    (field: "voice" | "avoid" | "prefer") => {
      setBrand((prev) => ({ ...prev, [field]: [...prev[field], ""] }));
      setDirty(true);
    },
    [],
  );

  const updateListItem = useCallback(
    (field: "voice" | "avoid" | "prefer", idx: number, value: string) => {
      setBrand((prev) => {
        const arr = [...prev[field]];
        arr[idx] = value;
        return { ...prev, [field]: arr };
      });
      setDirty(true);
      setSaved(false);
    },
    [],
  );

  const removeListItem = useCallback(
    (field: "voice" | "avoid" | "prefer", idx: number) => {
      setBrand((prev) => {
        const arr = prev[field].filter((_, i) => i !== idx);
        return { ...prev, [field]: arr };
      });
      setDirty(true);
      setSaved(false);
    },
    [],
  );

  return (
    <div className="max-w-3xl space-y-6 p-7">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Settings</h1>
        <button
          onClick={save}
          disabled={saving || !dirty}
          className="rounded-md bg-coral px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-coral-hover disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? "Saving…" : saved ? "Saved" : "Save Changes"}
        </button>
      </div>

      {/* System Info */}
      <Section title="System">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <InfoRow label="Model" value={health?.model ?? "—"} mono />
          <InfoRow label="Composio" value={health?.composio_configured ? "Connected" : "Not configured"} />
          <InfoRow label="Pipedream" value={health?.pipedream_configured ? "Connected" : "Not configured"} />
          <InfoRow label="Scheduler" value={health?.scheduler_running ? "Running" : "Stopped"} />
          <InfoRow label="Primitives" value={health?.primitives_dir ?? "—"} mono small />
        </div>
      </Section>

      {/* Integrations */}
      <Section title="Integrations">
        <div className="space-y-4">
          {integrations.map((int_) => (
            <IntegrationCard
              key={int_.name}
              integration={int_}
              draft={intKeyDrafts[int_.name] ?? ""}
              onDraftChange={(val) => {
                setIntKeyDrafts((prev) => ({ ...prev, [int_.name]: val }));
                setIntSaved(false);
              }}
            />
          ))}
          {integrations.length === 0 && (
            <p className="text-xs text-gray-400 italic">Loading integrations…</p>
          )}
          {Object.keys(intKeyDrafts).length > 0 && (
            <div className="flex items-center gap-3">
              <button
                onClick={saveIntegrationKeys}
                disabled={intSaving}
                className="rounded-md bg-coral px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-coral-hover disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {intSaving ? "Saving…" : "Save Keys"}
              </button>
            </div>
          )}
          {intSaved && <span className="text-xs text-emerald-600">Keys saved & reloaded</span>}
        </div>
      </Section>

      {/* Research Tool Keys */}
      <Section title="Research Tool Keys">
        <p className="mb-3 text-xs text-gray-500">
          API keys for research tools used during experiments. Tools without keys listed below work out of the box.
        </p>
        <div className="space-y-3">
          {toolKeys.map((tk) => (
            <ToolKeyCard
              key={tk.name}
              toolKey={tk}
              draft={toolKeyDrafts[tk.name] ?? ""}
              onDraftChange={(val) => {
                setToolKeyDrafts((prev) => ({ ...prev, [tk.name]: val }));
                setToolKeySaved(false);
              }}
            />
          ))}
          {toolKeys.length === 0 && (
            <p className="text-xs text-gray-400 italic">Loading tool keys…</p>
          )}
          {Object.keys(toolKeyDrafts).length > 0 && (
            <div className="flex items-center gap-3">
              <button
                onClick={saveToolKeys}
                disabled={toolKeySaving}
                className="rounded-md bg-coral px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-coral-hover disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {toolKeySaving ? "Saving…" : "Save Keys"}
              </button>
            </div>
          )}
          {toolKeySaved && <span className="text-xs text-emerald-600">Keys saved & reloaded</span>}
        </div>
        {noKeyTools.length > 0 && (
          <div className="mt-4 border-t border-black/[0.06] pt-3">
            <p className="mb-2 text-xs text-gray-500 uppercase tracking-wider">No Key Required</p>
            <div className="flex flex-wrap gap-2">
              {noKeyTools.map((t) => (
                <span
                  key={t.name}
                  className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] text-emerald-600"
                >
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  {t.label}
                </span>
              ))}
            </div>
          </div>
        )}
      </Section>

      {/* Brand Identity */}
      <Section title="Brand Identity">
        <div className="space-y-3">
          <Field label="Company Name" value={brand.company_name} onChange={(v) => update({ company_name: v })} placeholder="Acme Corp" />
          <Field label="Tagline" value={brand.tagline} onChange={(v) => update({ tagline: v })} placeholder="We help SaaS founders find their next 100 customers" />
          <Field label="Website" value={brand.website} onChange={(v) => update({ website: v })} placeholder="https://acme.com" />
          <TextArea label="What you sell (one sentence)" value={brand.product_description} onChange={(v) => update({ product_description: v })} placeholder="A single, plain sentence describing your product. No buzzwords." rows={2} />
        </div>
      </Section>

      {/* Social Links */}
      <Section title="Social Links">
        <div className="grid grid-cols-2 gap-3">
          {SOCIAL_KEYS.map((key) => (
            <Field
              key={key}
              label={key.charAt(0).toUpperCase() + key.slice(1)}
              value={brand.social[key] || ""}
              onChange={(v) => updateSocial(key, v)}
              placeholder={`https://${key}.com/yourhandle`}
            />
          ))}
        </div>
      </Section>

      {/* ICP */}
      <Section title="Ideal Customer Profile">
        <div className="space-y-3">
          <TextArea label="Who you talk to" value={brand.icp} onChange={(v) => update({ icp: v })} placeholder="Real buyers with real budgets (VP-level and above for B2B; owners / GMs for local SMB)." rows={3} />
          <TextArea label="Who you don't talk to" value={brand.icp_negative} onChange={(v) => update({ icp_negative: v })} placeholder="Students, analysts, journalists, random newsletter subscribers." rows={2} />
        </div>
      </Section>

      {/* Voice & Tone */}
      <Section title="Voice & Tone">
        <div className="space-y-4">
          <EditableList label="Voice traits" items={brand.voice} field="voice" onAdd={addListItem} onUpdate={updateListItem} onRemove={removeListItem} placeholder="e.g. direct, specific, warm" />
          <EditableList label="Words to avoid" items={brand.avoid} field="avoid" onAdd={addListItem} onUpdate={updateListItem} onRemove={removeListItem} placeholder="e.g. synergy, leverage, unlock" />
          <EditableList label="Writing preferences" items={brand.prefer} field="prefer" onAdd={addListItem} onUpdate={updateListItem} onRemove={removeListItem} placeholder="e.g. one idea per message" />
        </div>
      </Section>

      {/* Length Limits */}
      <Section title="Length Limits">
        <div className="grid grid-cols-2 gap-3">
          <NumberField label="Max sentences per email" value={brand.email_max_sentences} onChange={(v) => update({ email_max_sentences: v })} />
          <NumberField label="Max words per email" value={brand.email_max_words} onChange={(v) => update({ email_max_words: v })} />
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass-heavy rounded-2xl p-5">
      <h2 className="mb-3 text-sm font-semibold text-gray-500 uppercase tracking-wider">{title}</h2>
      {children}
    </div>
  );
}

function InfoRow({ label, value, mono, small }: { label: string; value: string; mono?: boolean; small?: boolean }) {
  return (
    <div>
      <span className="text-gray-500 text-xs">{label}</span>
      <div className={`${mono ? "font-mono" : ""} ${small ? "text-xs" : "text-sm"} text-gray-900`}>{value}</div>
    </div>
  );
}

function Field({
  label, value, onChange, placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-gray-500">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-black/[0.06] bg-black/[0.03] px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-coral/40 transition-colors"
      />
    </div>
  );
}

function TextArea({
  label, value, onChange, placeholder, rows = 3,
}: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; rows?: number;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-gray-500">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="w-full rounded-md border border-black/[0.06] bg-black/[0.03] px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-coral/40 transition-colors resize-y"
      />
    </div>
  );
}

function NumberField({
  label, value, onChange,
}: {
  label: string; value: number; onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-gray-500">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value, 10) || 0)}
        className="w-full rounded-md border border-black/[0.06] bg-black/[0.03] px-3 py-1.5 text-sm text-gray-900 outline-none focus:border-coral/40 transition-colors"
      />
    </div>
  );
}

function EditableList({
  label, items, field, onAdd, onUpdate, onRemove, placeholder,
}: {
  label: string;
  items: string[];
  field: "voice" | "avoid" | "prefer";
  onAdd: (field: "voice" | "avoid" | "prefer") => void;
  onUpdate: (field: "voice" | "avoid" | "prefer", idx: number, value: string) => void;
  onRemove: (field: "voice" | "avoid" | "prefer", idx: number) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <label className="text-xs text-gray-500">{label}</label>
        <button
          onClick={() => onAdd(field)}
          className="text-xs text-coral hover:text-coral-hover transition-colors"
        >
          + Add
        </button>
      </div>
      <div className="space-y-1.5">
        {items.map((item, idx) => (
          <div key={idx} className="flex items-center gap-1.5">
            <input
              type="text"
              value={item}
              onChange={(e) => onUpdate(field, idx, e.target.value)}
              placeholder={placeholder}
              className="flex-1 rounded-md border border-black/[0.06] bg-black/[0.03] px-3 py-1 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-coral/40 transition-colors"
            />
            <button
              onClick={() => onRemove(field, idx)}
              className="rounded p-1 text-gray-500 hover:bg-black/[0.04] hover:text-red-400 transition-colors"
            >
              ✕
            </button>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-xs text-gray-400 italic">No items yet. Click + Add to start.</p>
        )}
      </div>
    </div>
  );
}

function ToolKeyCard({
  toolKey,
  draft,
  onDraftChange,
}: {
  toolKey: ToolKeyInfo;
  draft: string;
  onDraftChange: (val: string) => void;
}) {
  const [showKey, setShowKey] = useState(false);

  return (
    <div className="glass-subtle rounded-2xl p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900">{toolKey.label}</span>
          <span
            className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${
              toolKey.configured
                ? "bg-emerald-500/10 text-emerald-600"
                : "bg-amber-500/10 text-amber-600"
            }`}
          >
            {toolKey.configured ? "Active" : "Missing"}
          </span>
        </div>
        <span className="text-[10px] text-gray-400">
          Used by: {toolKey.required_by.join(", ")}
        </span>
      </div>
      <p className="text-xs text-gray-500">{toolKey.description}</p>
      <div>
        <label className="mb-1 block text-xs text-gray-500">
          {toolKey.env_var}
          {toolKey.masked_key && (
            <span className="ml-2 text-gray-400">Current: {toolKey.masked_key}</span>
          )}
        </label>
        <div className="flex items-center gap-2">
          <input
            type={showKey ? "text" : "password"}
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            placeholder={toolKey.configured ? "Enter new key to update…" : "Paste your API key…"}
            className="flex-1 rounded-md border border-black/[0.06] glass-heavy px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-coral/40 transition-colors font-mono"
          />
          <button
            onClick={() => setShowKey((p) => !p)}
            className="rounded px-2 py-1 text-xs text-gray-500 hover:bg-black/[0.04] transition-colors"
          >
            {showKey ? "Hide" : "Show"}
          </button>
        </div>
      </div>
    </div>
  );
}

function IntegrationCard({
  integration,
  draft,
  onDraftChange,
}: {
  integration: Integration;
  draft: string;
  onDraftChange: (val: string) => void;
}) {
  const [showKey, setShowKey] = useState(false);

  return (
    <div className="glass-subtle rounded-2xl p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900">{integration.label}</span>
          <span
            className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${
              integration.configured
                ? "bg-emerald-500/10 text-emerald-600"
                : "bg-black/[0.04] text-gray-500"
            }`}
          >
            {integration.configured ? "Connected" : "Not configured"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={integration.docs_url}
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-gray-500 hover:text-gray-900 transition-colors"
          >
            Docs
          </a>
          <a
            href={integration.dashboard_url}
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-gray-500 hover:text-gray-900 transition-colors"
          >
            Dashboard
          </a>
        </div>
      </div>
      <p className="text-xs text-gray-500">{integration.description}</p>
      <div>
        <label className="mb-1 block text-xs text-gray-500">
          API Key ({integration.env_var})
          {integration.masked_key && (
            <span className="ml-2 text-gray-400">Current: {integration.masked_key}</span>
          )}
        </label>
        <div className="flex items-center gap-2">
          <input
            type={showKey ? "text" : "password"}
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            placeholder={integration.configured ? "Enter new key to update…" : "Paste your API key…"}
            className="flex-1 rounded-md border border-black/[0.06] glass-heavy px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-coral/40 transition-colors font-mono"
          />
          <button
            onClick={() => setShowKey((p) => !p)}
            className="rounded px-2 py-1 text-xs text-gray-500 hover:bg-black/[0.04] transition-colors"
          >
            {showKey ? "Hide" : "Show"}
          </button>
        </div>
      </div>
    </div>
  );
}
