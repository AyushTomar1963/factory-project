import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ExternalLink, FileText, Link2, Mail, ShieldAlert, ShieldCheck, Sparkles, UserSearch } from "lucide-react";
import { api, openFile, type ActionResult, type Contact } from "../api";
import { Button, Card, Chip, Empty, label, PageHeader, Spinner, StatusBadge, useApi, useToast, when } from "../ui";

type Detail = {
  lead: {
    id: number; source: string; title: string; company: string | null; season: string | null; location: string | null;
    status: string; url: string | null; description: string | null; poster_name: string | null; poster_url: string | null;
    posted_at: string | null; match_score: number | null; keywords: string[];
  };
  document: null | {
    cover_letter: string; pitch: string; engine: string; created_at: string; has_pdf: boolean; has_cover: boolean;
    violations: string[]; matched: string[]; missing: string[];
  };
  contacts: Contact[];
  outreach: { id: number; channel: string; kind: string; status: string; subject: string | null; replied_at: string | null; name: string; email: string | null }[];
};

const SOURCE_TEXT: Record<string, string> = {
  hiring_posts: "LinkedIn hiring post",
  linkedin_jobs: "LinkedIn internship listing",
  companies: "Your company list",
};

export default function LeadDetail() {
  const { id } = useParams();
  const toast = useToast();
  const { data, error, refresh } = useApi<Detail>(() => api(`/api/leads/${id}`), [id]);
  const [busy, setBusy] = useState<string | null>(null);

  const act = async (key: string, path: string, json?: unknown) => {
    setBusy(key);
    try {
      toast(await api<ActionResult>(path, { method: "POST", json }));
      await refresh();
    } catch (e) {
      toast((e as Error).message, false);
    } finally {
      setBusy(null);
    }
  };
  const open = (kind: string) => openFile(`/api/files/${id}/${kind}`).catch((e) => toast(e.message, false));

  if (error) return <Empty title="Couldn't load this lead">{error}</Empty>;
  if (!data) return <Spinner />;
  const { lead, document: doc } = data;

  return (
    <>
      <Link to="/leads" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="size-4" /> Leads
      </Link>
      <PageHeader
        title={lead.title}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <span>{lead.company ?? "Company not identified yet"}</span>
            {lead.season && <Chip>{lead.season}</Chip>}
            {lead.location && <Chip tone="gray">{lead.location}</Chip>}
            <StatusBadge status={lead.status} />
            <span className="text-slate-400">· {SOURCE_TEXT[lead.source] ?? lead.source}</span>
            {lead.url && (
              <a href={lead.url} target="_blank" rel="noopener" className="inline-flex items-center gap-1 text-brand-600 hover:underline">
                source <ExternalLink className="size-3" />
              </a>
            )}
          </span>
        }
        actions={
          <>
            <Button icon={<UserSearch className="size-4" />} loading={busy === "enrich"} onClick={() => act("enrich", `/api/leads/${id}/enrich`)}>
              Find people
            </Button>
            <Button variant="primary" icon={<Sparkles className="size-4" />} loading={busy === "tailor"} onClick={() => act("tailor", `/api/leads/${id}/tailor`)}>
              {doc ? "Re-craft resume" : "Craft resume"}
            </Button>
            {lead.status === "skipped" ? (
              <Button onClick={() => act("status", `/api/leads/${id}/status`, { status: "new" })}>Restore</Button>
            ) : (
              <Button variant="danger" onClick={() => act("status", `/api/leads/${id}/status`, { status: "skipped" })}>Skip</Button>
            )}
          </>
        }
      />

      {lead.poster_url && (
        <div className="card mb-6 flex items-center gap-3 p-4 text-sm">
          <div className="grid size-9 place-items-center rounded-full bg-sky-50 text-sky-600"><Link2 className="size-4" /></div>
          <div>
            Posted by <b>{lead.poster_name ?? "someone"}</b>
            {lead.posted_at && <span className="text-slate-500"> · {lead.posted_at.slice(0, 10)}</span>}
          </div>
          <a href={lead.poster_url} target="_blank" rel="noopener" className="ml-auto text-sm font-medium text-brand-600 hover:underline">Profile</a>
        </div>
      )}

      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <Card title={`Fit${lead.match_score != null ? ` · ${Math.round(lead.match_score * 100)}%` : ""}`}>
          {doc ? (
            <>
              <div className="mb-1.5 text-xs font-medium text-slate-500">You have</div>
              <div className="flex flex-wrap gap-1.5">{doc.matched.length ? doc.matched.map((k) => <Chip key={k}>{k}</Chip>) : <span className="text-xs text-slate-400">no overlap detected</span>}</div>
              <div className="mt-4 mb-1.5 text-xs font-medium text-slate-500">They mention, not on your resume (never added)</div>
              <div className="flex flex-wrap gap-1.5">{doc.missing.length ? doc.missing.map((k) => <Chip key={k} tone="red">{k}</Chip>) : <span className="text-xs text-slate-400">none</span>}</div>
            </>
          ) : lead.keywords.length ? (
            <div className="flex flex-wrap gap-1.5">{lead.keywords.map((k) => <Chip key={k} tone="gray">{k}</Chip>)}</div>
          ) : (
            <p className="text-sm text-slate-500">No specific skills mentioned.</p>
          )}
        </Card>

        <Card title="Tailored resume">
          {doc ? (
            <>
              <div className="flex flex-wrap gap-2">
                {doc.has_pdf && <Button variant="primary" size="sm" icon={<FileText className="size-3.5" />} onClick={() => open("resume.pdf")}>Resume PDF</Button>}
                <Button size="sm" onClick={() => open("resume.html")}>HTML</Button>
                {doc.has_cover && <Button size="sm" onClick={() => open("cover.pdf")}>Cover letter</Button>}
              </div>
              <p className="mt-3 text-xs text-slate-500">{doc.engine} · {when(doc.created_at)}</p>
              {doc.violations.length ? (
                <div className="mt-3 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">
                  <div className="mb-1 flex items-center gap-1.5 font-medium"><ShieldAlert className="size-4" /> Fact guard rejected {doc.violations.length} suggestion(s) and kept your wording</div>
                  <ul className="list-disc space-y-0.5 pl-5">{doc.violations.map((v) => <li key={v}>{v}</li>)}</ul>
                </div>
              ) : (
                <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-emerald-700"><ShieldCheck className="size-4" /> Everything traces back to your resume.</p>
              )}
            </>
          ) : (
            <Empty icon={<FileText className="size-5" />} title="Not crafted yet">Click "Craft resume" to build one for this lead.</Empty>
          )}
        </Card>
      </div>

      {doc && (
        <div className="mb-6 grid gap-6 lg:grid-cols-2">
          <Card title="Email pitch"><p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-700">{doc.pitch}</p></Card>
          <Card title="Cover letter"><p className="max-h-80 overflow-auto text-sm leading-relaxed whitespace-pre-wrap text-slate-700">{doc.cover_letter}</p></Card>
        </div>
      )}

      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <Card title="People to contact">
          {data.contacts.length ? (
            <div className="divide-y divide-slate-100">
              {data.contacts.map((c) => (
                <div key={c.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-800">{c.name}</div>
                    <div className="truncate text-xs text-slate-500">{c.title ?? ""}</div>
                  </div>
                  <div className="text-right text-xs">
                    {c.email ? (
                      <span className="inline-flex items-center gap-1 text-slate-700"><Mail className="size-3.5" />{c.email} <span className="text-slate-400">{c.email_confidence ?? "?"}%</span></span>
                    ) : c.linkedin_url ? (
                      <a href={c.linkedin_url} target="_blank" rel="noopener" className="inline-flex items-center gap-1 text-brand-600"><Link2 className="size-3.5" /> LinkedIn only</a>
                    ) : (
                      <span className="text-slate-400">no channel</span>
                    )}
                    <div className="text-slate-400">{c.source}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Empty icon={<UserSearch className="size-5" />} title="Nobody found yet">Click "Find people" (needs Apollo or Hunter).</Empty>
          )}
        </Card>
        <Card title="Emails">
          {data.outreach.length ? (
            <div className="divide-y divide-slate-100">
              {data.outreach.map((o) => (
                <Link key={o.id} to={`/emails?status=${o.status}`} className="-mx-2 flex items-center justify-between gap-3 rounded-lg px-2 py-2.5 hover:bg-slate-50">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-800">{o.name}</div>
                    <div className="truncate text-xs text-slate-500">{o.channel} · {label(o.kind)} {o.subject && `· ${o.subject}`}</div>
                  </div>
                  <div className="flex gap-1">
                    <StatusBadge status={o.status} />
                    {o.replied_at && <StatusBadge status="replied" />}
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <Empty icon={<Mail className="size-5" />} title="No drafts yet" />
          )}
        </Card>
      </div>

      {lead.description && (
        <Card title="Details"><p className="max-h-96 overflow-auto text-sm leading-relaxed whitespace-pre-wrap text-slate-600">{lead.description}</p></Card>
      )}
    </>
  );
}
