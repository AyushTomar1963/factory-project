import { useState } from "react";
import { Ban, Check, Inbox, Send, ShieldCheck, X } from "lucide-react";
import { api, type ActionResult, type Allowance, type RunStatus } from "../api";
import { ago, Button, Card, Chip, Empty, PageHeader, Spinner, useApi, useToast } from "../ui";

type DomainCheck = { name: string; ok: boolean; required: boolean; detail: string };
type SendingData = RunStatus & {
  sender: string;
  imap: boolean;
  allowance: Allowance | null;
  report: { ok: boolean; checks: DomainCheck[] } | null;
  approved: number;
  log: { id: number; recipient: string; outcome: string; detail: string | null; at: string }[];
  suppressed: { email: string; reason: string; created_at: string }[];
  replies: { id: number; subject: string | null; replied_at: string; name: string; email: string; company: string | null }[];
  outreach: { daily_cap: number; min_delay_seconds: number; max_delay_seconds: number; recontact_after_days: number; max_bounce_rate: number; attach_resume: boolean };
};

export default function SendingPage() {
  const toast = useToast();
  const [check, setCheck] = useState(0);
  const { data, refresh } = useApi<SendingData>(() => api(`/api/sending?check=${check}`), [check], (d) => (d?.send.running ? 3000 : null));
  const [busy, setBusy] = useState<string | null>(null);
  const [email, setEmail] = useState("");

  const act = async (key: string, fn: () => Promise<ActionResult>) => {
    setBusy(key);
    try {
      toast(await fn());
      await refresh();
    } catch (e) {
      toast((e as Error).message, false);
    } finally {
      setBusy(null);
    }
  };

  if (!data) return <Spinner />;
  const a = data.allowance;
  const o = data.outreach;

  return (
    <>
      <PageHeader
        title="Sending"
        subtitle={data.sender ? <>Emails go out from <b className="text-slate-700">{data.sender}</b>, throttled and warmed up so they don't hurt your domain.</> : "Set SMTP and SENDER_EMAIL on Render to start sending."}
        actions={
          <Button
            variant="primary"
            icon={<Send className="size-4" />}
            loading={busy === "send" || data.send.running}
            disabled={!data.approved}
            onClick={() => act("send", () => api("/api/actions/send", { method: "POST" }))}
          >
            Send {data.approved} approved
          </Button>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-4">
        {[
          ["Sent today", a ? `${a.sent_today}/${a.cap}` : "n/a"],
          ["Left today", a ? a.remaining : "n/a"],
          ["Warm-up day", a ? a.warmup_day : "n/a"],
          ["Bounce rate", a ? `${(a.bounce_rate * 100).toFixed(1)}%` : "n/a"],
        ].map(([k, v]) => (
          <div key={k} className="card p-4">
            <div className="text-xs text-slate-500">{k}</div>
            <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{v}</div>
          </div>
        ))}
      </div>
      {a?.paused_reason && <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">Sending is paused: {a.paused_reason}</div>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {(data.send.running || data.send.log.length > 0) && (
            <Card title={data.send.running ? "Sending now…" : "Last send"} action={data.send.summary && <Chip tone="green">{data.send.summary}</Chip>}>
              <pre className="max-h-64 overflow-auto rounded-xl bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100">{data.send.log.join("\n") || "starting…"}</pre>
            </Card>
          )}

          <Card
            title="Replies"
            action={
              <Button size="sm" icon={<Inbox className="size-3.5" />} disabled={!data.imap} loading={busy === "inbox"} onClick={() => act("inbox", () => api("/api/sending/check-inbox", { method: "POST" }))}>
                Check inbox
              </Button>
            }
          >
            {data.replies.length === 0 ? (
              <Empty title="No replies yet">{data.imap ? "Replies and bounces are picked up from your inbox automatically." : "Set IMAP_HOST to detect replies automatically."}</Empty>
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.replies.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-slate-800">
                        {r.name} <span className="font-normal text-slate-400">· {r.company}</span>
                      </div>
                      <div className="truncate text-xs text-slate-500">{r.subject}</div>
                    </div>
                    <span className="shrink-0 text-xs text-slate-400">{ago(r.replied_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Send log">
            {data.log.length === 0 ? (
              <Empty title="Nothing sent yet" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-slate-500">
                    <tr>
                      <th className="pb-2 font-medium">To</th>
                      <th className="pb-2 font-medium">Outcome</th>
                      <th className="pb-2 font-medium">When</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.log.map((l) => (
                      <tr key={l.id}>
                        <td className="py-2 pr-3 text-slate-700">{l.recipient}</td>
                        <td className="py-2 pr-3">
                          <Chip tone={l.outcome === "sent" ? "green" : l.outcome === "bounced" || l.outcome === "failed" ? "red" : "gray"}>{l.outcome}</Chip>
                          {l.detail && <span className="ml-2 text-xs text-slate-400">{l.detail}</span>}
                        </td>
                        <td className="py-2 text-xs whitespace-nowrap text-slate-400">{ago(l.at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card
            title={
              <span className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-slate-400" /> Domain health
              </span>
            }
            action={
              <Button size="sm" onClick={() => (check ? refresh() : setCheck(1))}>
                {data.report ? "Re-check" : "Check"}
              </Button>
            }
          >
            {data.report ? (
              <ul className="space-y-2.5">
                {data.report.checks.map((c) => (
                  <li key={c.name} className="flex gap-2.5 text-sm">
                    {c.ok ? <Check className="mt-0.5 size-4 shrink-0 text-emerald-500" /> : <X className={`mt-0.5 size-4 shrink-0 ${c.required ? "text-rose-500" : "text-amber-500"}`} />}
                    <div>
                      <div className="font-medium text-slate-800">
                        {c.name} {!c.required && <span className="text-xs font-normal text-slate-400">optional</span>}
                      </div>
                      <div className="text-xs break-all text-slate-500">{c.detail}</div>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">Checks SPF, DKIM and DMARC for your sender domain. Sending is blocked until the required ones pass.</p>
            )}
          </Card>

          <Card title="Limits">
            <dl className="space-y-2 text-sm">
              {[
                ["Daily cap", o.daily_cap],
                ["Gap between emails", `${o.min_delay_seconds}–${o.max_delay_seconds}s`],
                ["Don't re-email for", `${o.recontact_after_days} days`],
                ["Pause above bounce rate", `${(o.max_bounce_rate * 100).toFixed(0)}%`],
                ["Attach resume PDF", o.attach_resume ? "yes" : "no"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="font-medium text-slate-800">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>

          <Card
            title={
              <span className="flex items-center gap-2">
                <Ban className="size-4 text-slate-400" /> Never email
              </span>
            }
          >
            <form
              className="mb-3 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                act("suppress", () => api("/api/sending/suppress", { method: "POST", json: { email } })).then(() => setEmail(""));
              }}
            >
              <input className="input" type="email" placeholder="someone@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
              <Button type="submit" loading={busy === "suppress"} disabled={!email}>
                Add
              </Button>
            </form>
            {data.suppressed.length === 0 ? (
              <p className="hint">Unsubscribes and bounces are added automatically.</p>
            ) : (
              <ul className="max-h-64 space-y-1.5 overflow-auto text-sm">
                {data.suppressed.map((s) => (
                  <li key={s.email} className="flex justify-between gap-2">
                    <span className="truncate text-slate-700">{s.email}</span>
                    <span className="shrink-0 text-xs text-slate-400">{s.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
