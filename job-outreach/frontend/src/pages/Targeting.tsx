import { useEffect, useState } from "react";
import { Check, Circle, Clock, Copy, ExternalLink, Save } from "lucide-react";
import { api, type ActionResult, type SetupItem, type Targeting } from "../api";
import { Button, Card, Chip, cx, PageHeader, Spinner, Toggle, useApi, useToast } from "../ui";

type SettingsData = {
  targeting: Targeting;
  sources: Record<string, string>;
  setup: SetupItem[];
  cron_configured: boolean;
  min_email_confidence: number;
};

const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

function ListField({ label, hint, value, onChange, placeholder, rows = 3 }: { label: string; hint?: string; value: string[]; onChange: (v: string[]) => void; placeholder?: string; rows?: number }) {
  const [text, setText] = useState(value.join("\n"));
  useEffect(() => setText(value.join("\n")), [value.join("\n")]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div>
      <label className="label">{label}</label>
      <textarea className="input font-mono text-xs" rows={rows} placeholder={placeholder} value={text} onChange={(e) => setText(e.target.value)} onBlur={() => onChange(lines(text))} />
      {hint && <p className="hint mt-1">{hint}</p>}
    </div>
  );
}

function NumberField({ label, hint, value, onChange, min, max }: { label: string; hint?: string; value: number; onChange: (v: number) => void; min?: number; max?: number }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input type="number" className="input" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      {hint && <p className="hint mt-1">{hint}</p>}
    </div>
  );
}

export default function TargetingPage() {
  const toast = useToast();
  const { data, setData } = useApi<SettingsData>(() => api("/api/settings"), []);
  const [t, setT] = useState<Targeting | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (data) setT(data.targeting);
  }, [data]);

  if (!data || !t) return <Spinner />;
  const set = <K extends keyof Targeting>(k: K, v: Targeting[K]) => setT({ ...t, [k]: v });
  const dirty = JSON.stringify(t) !== JSON.stringify(data.targeting);
  const cronUrl = `${window.location.origin}/cron/tick?key=YOUR_CRON_SECRET`;

  const save = async () => {
    setSaving(true);
    try {
      const r = await api<ActionResult & { targeting?: Targeting }>("/api/settings", { method: "PUT", json: t });
      toast(r);
      if (r.ok && r.targeting) {
        setData({ ...data, targeting: r.targeting });
      }
    } catch (e) {
      toast((e as Error).message, false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Targeting"
        subtitle="What to hunt for and how hard to push. Saved in the database, so changes apply to the next cycle."
        actions={
          <Button variant="primary" icon={<Save className="size-4" />} loading={saving} disabled={!dirty} onClick={save}>
            {dirty ? "Save changes" : "Saved"}
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Internships">
            <div className="grid gap-5 sm:grid-cols-2">
              <ListField label="Seasons" hint="One per line, e.g. Summer 2027" value={t.seasons} onChange={(v) => set("seasons", v)} />
              <ListField label="Roles" hint="One per line" value={t.roles} onChange={(v) => set("roles", v)} />
              <ListField label="Locations" hint="Leave empty for anywhere, or add Remote" value={t.locations} onChange={(v) => set("locations", v)} placeholder={"Bengaluru\nRemote"} />
              <ListField
                label="Companies to cold-email"
                hint="Company Name, domain.com, one per line"
                value={t.companies}
                onChange={(v) => set("companies", v)}
                placeholder={"Razorpay, razorpay.com\npostman.com"}
              />
            </div>
            <div className="mt-4 border-t border-slate-100 pt-2">
              <Toggle checked={t.require_season} onChange={(v) => set("require_season", v)} label="Only seasonal internships" hint="Skip posts that don't mention summer or winter" />
            </div>
          </Card>

          <Card title="Lead sources">
            <div className="space-y-2">
              {Object.entries(data.sources).map(([key, desc]) => {
                const on = t.sources.includes(key);
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => set("sources", on ? t.sources.filter((s) => s !== key) : [...t.sources, key])}
                    className={cx("flex w-full items-center gap-3 rounded-xl border p-3 text-left transition", on ? "border-brand-500 bg-brand-50/50" : "border-slate-200 hover:border-slate-300")}
                  >
                    <span className={cx("flex size-5 items-center justify-center rounded-md border", on ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300")}>{on && <Check className="size-3.5" />}</span>
                    <span>
                      <span className="block text-sm font-medium text-slate-800">{key.replace(/_/g, " ")}</span>
                      <span className="block text-xs text-slate-500">{desc}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="mt-4 max-w-xs">
              <NumberField label="Results per search" min={5} max={100} value={t.max_results_per_query} onChange={(v) => set("max_results_per_query", v)} />
            </div>
          </Card>

          <Card title="Auto-emailer">
            <Toggle checked={t.auto_send} onChange={(v) => set("auto_send", v)} label="Send without asking" hint="Off means drafts wait for your approval on the Emails page" />
            <Toggle checked={t.followups_enabled} onChange={(v) => set("followups_enabled", v)} label="Follow up once if there's no reply" />
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <NumberField label="Run a cycle every (hours)" min={1} value={t.cycle_every_hours} onChange={(v) => set("cycle_every_hours", v)} />
              <NumberField label="Resumes to tailor per cycle" min={1} max={50} value={t.tailor_per_cycle} onChange={(v) => set("tailor_per_cycle", v)} />
              <NumberField label="Emails per tick" hint="Each cron ping sends at most this many" min={1} max={10} value={t.per_tick} onChange={(v) => set("per_tick", v)} />
              <NumberField label="Follow up after (days)" min={2} value={t.followup_after_days} onChange={(v) => set("followup_after_days", v)} />
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Keys and setup">
            <ul className="space-y-3">
              {data.setup.map((s) => (
                <li key={s.name} className="flex gap-3">
                  {s.ok ? <Check className="mt-0.5 size-4 shrink-0 text-emerald-500" /> : <Circle className="mt-0.5 size-4 shrink-0 text-slate-300" />}
                  <div>
                    <div className={cx("text-sm font-medium", s.ok ? "text-slate-500" : "text-slate-800")}>{s.name}</div>
                    {!s.ok && (
                      <div className="text-xs text-slate-500">
                        {s.how}
                        {s.href && (
                          <a href={s.href} target="_blank" rel="noreferrer" className="ml-1 inline-flex items-center gap-0.5 text-brand-600 hover:underline">
                            open <ExternalLink className="size-3" />
                          </a>
                        )}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            <p className="hint mt-4">Keys are environment variables on the Render service, never stored in the browser.</p>
          </Card>

          <Card
            title={
              <span className="flex items-center gap-2">
                <Clock className="size-4 text-slate-400" /> Keep it running
              </span>
            }
            action={data.cron_configured ? <Chip tone="green">CRON_SECRET set</Chip> : <Chip tone="red">CRON_SECRET missing</Chip>}
          >
            <p className="text-sm text-slate-600">
              The free server sleeps. Create a job on <a className="text-brand-600 hover:underline" href="https://cron-job.org" target="_blank" rel="noreferrer">cron-job.org</a> that opens this URL every 10 minutes:
            </p>
            <div className="mt-3 flex items-center gap-2 rounded-xl bg-slate-900 p-3 font-mono text-xs text-slate-100">
              <span className="min-w-0 flex-1 truncate">{cronUrl}</span>
              <button
                className="text-slate-400 hover:text-white"
                onClick={() => {
                  navigator.clipboard.writeText(cronUrl);
                  toast("Copied");
                }}
              >
                <Copy className="size-4" />
              </button>
            </div>
            <p className="hint mt-2">Each ping wakes the server, sends a few approved emails, and starts a new cycle when one is due.</p>
          </Card>
        </div>
      </div>
    </>
  );
}
