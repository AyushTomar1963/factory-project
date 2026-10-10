import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Braces, FileText, RotateCcw, Save, Sparkles, Upload } from "lucide-react";
import { api, blobUrl, openFile, type ActionResult } from "../api";
import { Button, Card, Chip, PageHeader, Spinner, Tabs, useApi, useToast } from "../ui";

type ResumeData = { saved: boolean; resume: Record<string, any> | null; warnings: string[]; llm: boolean };

export default function ResumePage() {
  const toast = useToast();
  const { data, setData } = useApi<ResumeData>(() => api("/api/resume"), []);
  const [json, setJson] = useState("");
  const [mode, setMode] = useState<"file" | "text">("file");
  const [pasted, setPasted] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [previewKey, setPreviewKey] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (data?.resume) setJson(JSON.stringify(data.resume, null, 2));
  }, [data?.resume]);

  useEffect(() => {
    if (!data?.resume) return;
    const ctrl = new AbortController();
    let url: string | null = null;
    blobUrl("/api/resume/preview?fmt=html", ctrl.signal)
      .then((u) => {
        url = u;
        setPreviewUrl(u);
      })
      .catch(() => setPreviewUrl(null));
    return () => {
      ctrl.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [data?.resume, previewKey]);

  const parsed = (() => {
    try {
      return { ok: true as const, value: JSON.parse(json) };
    } catch (e) {
      return { ok: false as const, error: (e as Error).message };
    }
  })();

  const importResume = async () => {
    const form = new FormData();
    if (mode === "file") {
      if (!file) return toast("Choose a PDF, TXT or Markdown file first", false);
      form.append("file", file);
    } else {
      if (!pasted.trim()) return toast("Paste your resume text first", false);
      form.append("text", pasted);
    }
    setBusy("import");
    try {
      const r = await api<ActionResult & { resume?: Record<string, any>; warnings?: string[] }>("/api/resume/import", { method: "POST", form });
      toast(r);
      if (r.ok && r.resume) {
        setData({ ...(data as ResumeData), saved: true, resume: r.resume, warnings: r.warnings ?? [] });
        setPreviewKey((k) => k + 1);
      }
    } catch (e) {
      toast((e as Error).message, false);
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    if (!parsed.ok) return toast(`Invalid JSON: ${parsed.error}`, false);
    setBusy("save");
    try {
      const r = await api<ActionResult & { resume?: Record<string, any> }>("/api/resume", { method: "PUT", json: parsed.value });
      toast(r);
      if (r.ok && r.resume) {
        setData({ ...(data as ResumeData), saved: true, resume: r.resume, warnings: [] });
        setPreviewKey((k) => k + 1);
      }
    } catch (e) {
      toast((e as Error).message, false);
    } finally {
      setBusy(null);
    }
  };

  const reset = async () => {
    if (!confirm("Discard your resume and go back to the bundled example?")) return;
    setBusy("reset");
    try {
      const r = await api<ActionResult & { resume?: Record<string, any> }>("/api/resume", { method: "DELETE" });
      toast(r);
      setData({ ...(data as ResumeData), saved: false, resume: r.resume ?? null, warnings: [] });
      setPreviewKey((k) => k + 1);
    } catch (e) {
      toast((e as Error).message, false);
    } finally {
      setBusy(null);
    }
  };

  const pdf = async () => {
    try {
      await openFile("/api/resume/preview?fmt=pdf");
    } catch (e) {
      toast((e as Error).message, false);
    }
  };

  if (!data) return <Spinner />;
  const r = data.resume ?? {};
  const stats = [
    ["Experience", (r.experience ?? []).length],
    ["Projects", (r.projects ?? []).length],
    ["Skills", Object.values(r.skills ?? {}).flat().length || (Array.isArray(r.skills) ? r.skills.length : 0)],
    ["Education", (r.education ?? []).length],
  ] as const;

  return (
    <>
      <PageHeader
        title="Master resume"
        subtitle="Every tailored resume is built from this one. The crafter only reorders and rephrases it, and it never adds skills or numbers that aren't here."
        actions={
          <>
            <Button icon={<FileText className="size-4" />} onClick={pdf} disabled={!data.resume}>
              Open PDF
            </Button>
            <Button variant="danger" icon={<RotateCcw className="size-4" />} loading={busy === "reset"} onClick={reset} disabled={!data.saved}>
              Reset
            </Button>
          </>
        }
      />

      {!data.saved && (
        <div className="mb-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 size-5 shrink-0" />
          <div>You're using the bundled example resume. Import your own below before sending anything.</div>
        </div>
      )}
      {data.warnings.length > 0 && (
        <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <div className="mb-1 font-medium">Check these after import</div>
          <ul className="list-disc space-y-0.5 pl-5">
            {data.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Import" action={<Tabs value={mode} onChange={setMode} items={[{ value: "file", label: "Upload" }, { value: "text", label: "Paste" }]} />}>
            {mode === "file" ? (
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                className="flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 px-4 py-8 text-center transition hover:border-brand-500 hover:bg-brand-50/40"
              >
                <Upload className="mb-2 size-6 text-slate-400" />
                <span className="text-sm font-medium text-slate-700">{file ? file.name : "Choose your resume"}</span>
                <span className="hint">PDF, TXT or Markdown</span>
                <input ref={fileInput} type="file" accept=".pdf,.txt,.md,.markdown" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </button>
            ) : (
              <textarea className="input h-48 font-mono text-xs" placeholder="Paste the plain text of your resume…" value={pasted} onChange={(e) => setPasted(e.target.value)} />
            )}
            <div className="mt-4 flex items-center justify-between gap-3">
              <span className="hint flex items-center gap-1">
                <Sparkles className="size-3.5" />
                {data.llm ? "The AI will structure it" : "No LLM key, so a basic parser is used"}
              </span>
              <Button variant="primary" loading={busy === "import"} onClick={importResume} icon={<Upload className="size-4" />}>
                Import
              </Button>
            </div>
          </Card>

          <Card title="At a glance">
            <div className="mb-4">
              <div className="text-lg font-semibold text-slate-900">{r.name ?? "Unnamed"}</div>
              <div className="text-sm text-slate-500">{[r.email, r.phone, r.location].filter(Boolean).join(" · ")}</div>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {stats.map(([k, v]) => (
                <div key={k} className="rounded-xl bg-slate-50 p-3 text-center">
                  <div className="text-lg font-semibold tabular-nums text-slate-900">{v}</div>
                  <div className="text-[11px] text-slate-500">{k}</div>
                </div>
              ))}
            </div>
            {data.saved ? <Chip tone="green">Your resume</Chip> : <Chip tone="gray">Example</Chip>}
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-3">
          <Card
            title={
              <span className="flex items-center gap-2">
                <Braces className="size-4 text-slate-400" /> Edit as JSON
              </span>
            }
            action={
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" disabled={!parsed.ok} onClick={() => parsed.ok && setJson(JSON.stringify(parsed.value, null, 2))}>
                  Format
                </Button>
                <Button size="sm" variant="primary" icon={<Save className="size-3.5" />} loading={busy === "save"} disabled={!parsed.ok} onClick={save}>
                  Save
                </Button>
              </div>
            }
          >
            <textarea spellCheck={false} className="input h-96 font-mono text-xs leading-relaxed" value={json} onChange={(e) => setJson(e.target.value)} />
            {!parsed.ok && <p className="mt-2 text-xs text-rose-600">{parsed.error}</p>}
          </Card>

          <Card title="Preview" className="p-0! overflow-hidden">
            {previewUrl ? (
              <iframe title="Resume preview" src={previewUrl} className="h-[720px] w-full border-t border-slate-100 bg-white" />
            ) : (
              <div className="px-5 pb-5 text-sm text-slate-500">Preview unavailable.</div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
