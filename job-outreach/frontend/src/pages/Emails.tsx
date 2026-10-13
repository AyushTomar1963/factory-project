import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCheck, Copy, ExternalLink, Link2, Mail, MailCheck, Paperclip } from "lucide-react";
import { api, type ActionResult, type OutreachRow } from "../api";
import { Button, Chip, Empty, PageHeader, Spinner, StatusBadge, Tabs, useApi, useToast, when } from "../ui";

const STATUSES = ["draft", "approved", "sent", "done", "rejected", "skipped", "bounced", "failed", "all"] as const;

export default function Emails() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "draft";
  const channel = params.get("channel") ?? "all";
  const toast = useToast();
  const { data, refresh } = useApi<{ rows: OutreachRow[]; counts: Record<string, number> }>(
    () => api(`/api/outreach?status=${status}&channel=${channel}`),
    [status, channel],
  );
  const [approving, setApproving] = useState(false);

  const set = (k: string, v: string) => {
    const n = new URLSearchParams(params);
    n.set(k, v);
    setParams(n, { replace: true });
  };

  const approveAll = async () => {
    if (!confirm("Approve every email draft?")) return;
    setApproving(true);
    try {
      toast(await api<ActionResult>("/api/outreach/approve-all", { method: "POST" }));
      await refresh();
    } finally {
      setApproving(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Emails"
        subtitle="Drafts wait here until approved, either by you or by autopilot for verified addresses when auto-send is on. LinkedIn notes are for you to send by hand."
        actions={
          status === "draft" && (data?.counts.draft ?? 0) > 0 ? (
            <Button variant="success" icon={<CheckCheck className="size-4" />} loading={approving} onClick={approveAll}>
              Approve all drafts
            </Button>
          ) : undefined
        }
      />
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs value={status} onChange={(v) => set("status", v)} items={STATUSES.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1), count: s === "all" ? undefined : data?.counts[s] ?? 0 }))} />
        <Tabs value={channel} onChange={(v) => set("channel", v)} items={["all", "email", "linkedin"].map((c) => ({ value: c, label: c[0].toUpperCase() + c.slice(1) }))} />
      </div>

      {!data ? (
        <Spinner />
      ) : data.rows.length === 0 ? (
        <div className="card"><Empty icon={<Mail className="size-5" />} title="Nothing here">Run a cycle from the overview to draft emails.</Empty></div>
      ) : (
        <div className="space-y-4">
          {data.rows.map((o) => <EmailCard key={o.id} o={o} onChange={refresh} />)}
        </div>
      )}
    </>
  );
}

function EmailCard({ o, onChange }: { o: OutreachRow; onChange: () => void }) {
  const toast = useToast();
  const [subject, setSubject] = useState(o.subject ?? "");
  const [body, setBody] = useState(o.body);
  const [busy, setBusy] = useState<string | null>(null);
  const editable = o.status === "draft";
  const dirty = subject !== (o.subject ?? "") || body !== o.body;

  const act = async (action: string) => {
    setBusy(action);
    try {
      const r = await api<ActionResult>(`/api/outreach/${o.id}`, { method: "POST", json: { action, subject: o.channel === "email" ? subject : undefined, body } });
      toast(r);
      if (r.ok) onChange();
    } catch (e) {
      toast((e as Error).message, false);
    } finally {
      setBusy(null);
    }
  };

  return (
    <article className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-100 to-violet-100 text-sm font-semibold text-brand-700">
            {o.name.slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="font-medium text-slate-900">
              {o.name} <span className="font-normal text-slate-500">{o.contact_title ?? ""}</span>
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-slate-500">
              <span>{o.company ?? "company unknown"}</span>·
              <Link to={`/leads/${o.lead_id}`} className="text-brand-600 hover:underline">{o.lead_title}</Link>
              {o.season && <>· {o.season}</>}·
              {o.channel === "email" ? (
                <span>{o.email} <span className="text-slate-400">({o.email_confidence ?? "?"}% via {o.contact_source})</span></span>
              ) : (
                <a href={o.linkedin_url ?? "#"} target="_blank" rel="noopener" className="text-brand-600">LinkedIn profile</a>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <Chip tone="gray">{o.channel === "email" ? <Mail className="mr-1 size-3" /> : <Link2 className="mr-1 size-3" />}{o.kind === "followup" ? "follow-up" : o.channel}</Chip>
          <StatusBadge status={o.status} />
          {o.replied_at && <StatusBadge status="replied" />}
        </div>
      </div>
      {o.error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{o.error}</p>}

      <div className="mt-4 space-y-2">
        {o.channel === "email" && (
          <input className="input font-medium" value={subject} disabled={!editable} onChange={(e) => setSubject(e.target.value)} />
        )}
        <textarea
          className="input min-h-44 font-mono text-[13px] leading-relaxed"
          value={body}
          disabled={!editable}
          maxLength={o.channel === "linkedin" ? 300 : undefined}
          onChange={(e) => setBody(e.target.value)}
        />
        {o.channel === "linkedin" ? (
          <p className="text-xs text-slate-400">{body.length}/300 characters</p>
        ) : (
          <p className="flex items-center gap-1.5 text-xs text-slate-400"><Paperclip className="size-3.5" /> The resume crafted for this lead is attached, plus an unsubscribe footer.</p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {o.status === "draft" && (
          <>
            {o.channel === "email" ? (
              <Button variant="success" icon={<MailCheck className="size-4" />} loading={busy === "approve"} onClick={() => act("approve")}>Approve</Button>
            ) : (
              <>
                <Button variant="primary" icon={<Copy className="size-4" />} onClick={() => { navigator.clipboard.writeText(body); toast("Copied"); }}>Copy note</Button>
                {o.linkedin_url && <a href={o.linkedin_url} target="_blank" rel="noopener"><Button icon={<ExternalLink className="size-4" />}>Open profile</Button></a>}
                <Button variant="success" loading={busy === "done"} onClick={() => act("done")}>I sent it</Button>
              </>
            )}
            <Button disabled={!dirty} loading={busy === "save"} onClick={() => act("save")}>Save edits</Button>
            <Button variant="danger" loading={busy === "reject"} onClick={() => act("reject")}>Reject</Button>
          </>
        )}
        {o.status === "approved" && <Button loading={busy === "unapprove"} onClick={() => act("unapprove")}>Move back to draft</Button>}
        {o.sent_at && <span className="text-xs text-slate-500">Sent {when(o.sent_at)}</span>}
      </div>
    </article>
  );
}
