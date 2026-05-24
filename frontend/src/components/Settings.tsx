import { useCallback, useEffect, useState } from "react";
import { BrandIdentity, getBrand, getHealth, updateBrand } from "../lib/api";

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


  useEffect(() => {
    getHealth().then(setHealth).catch(() => null);
    getBrand()
      .then((b) => setBrand(b))
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
    <div className="max-w-3xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Settings</h1>
        <button
          onClick={save}
          disabled={saving || !dirty}
          className="rounded-md bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed"
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
    <div className="rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-4">
      <h2 className="mb-3 text-sm font-semibold text-[#A1A1AA] uppercase tracking-wider">{title}</h2>
      {children}
    </div>
  );
}

function InfoRow({ label, value, mono, small }: { label: string; value: string; mono?: boolean; small?: boolean }) {
  return (
    <div>
      <span className="text-[#A1A1AA] text-xs">{label}</span>
      <div className={`${mono ? "font-mono" : ""} ${small ? "text-xs" : "text-sm"} text-[#FAFAFA]`}>{value}</div>
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
      <label className="mb-1 block text-xs text-[#A1A1AA]">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-1.5 text-sm text-[#FAFAFA] placeholder-[#555] outline-none focus:border-emerald-600 transition-colors"
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
      <label className="mb-1 block text-xs text-[#A1A1AA]">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="w-full rounded-md border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-1.5 text-sm text-[#FAFAFA] placeholder-[#555] outline-none focus:border-emerald-600 transition-colors resize-y"
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
      <label className="mb-1 block text-xs text-[#A1A1AA]">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value, 10) || 0)}
        className="w-full rounded-md border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-1.5 text-sm text-[#FAFAFA] outline-none focus:border-emerald-600 transition-colors"
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
        <label className="text-xs text-[#A1A1AA]">{label}</label>
        <button
          onClick={() => onAdd(field)}
          className="text-xs text-emerald-500 hover:text-emerald-400 transition-colors"
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
              className="flex-1 rounded-md border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-1 text-sm text-[#FAFAFA] placeholder-[#555] outline-none focus:border-emerald-600 transition-colors"
            />
            <button
              onClick={() => onRemove(field, idx)}
              className="rounded p-1 text-[#A1A1AA] hover:bg-[#2A2A2A] hover:text-red-400 transition-colors"
            >
              ✕
            </button>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-xs text-[#555] italic">No items yet. Click + Add to start.</p>
        )}
      </div>
    </div>
  );
}


