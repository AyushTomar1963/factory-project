import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Bot, Check, Circle, Inbox, Mail, MessageSquareReply, Play, RefreshCw, Rocket, Search, Users, Zap } from "lucide-react";
import { api, type ActionResult, type Allowance, type AutopilotState, type LeadRow, type RunStatus, type SetupItem, type Targeting } from "../api";
import { ago, Button, Card, Chip, cx, Empty, label, PageHeader, Spinner, StatusBadge, useApi, useToast, when } from "../ui";

type Overview = RunStatus & {
  stats: { leads: Record<string, number>; outreach: Record<string, number>; contacts: number; contacts_with_email: number; replies: number };
  setup: SetupItem[];
  targeting: Targeting;
  autopilot: AutopilotState;
  allowance: Allowance | null;
  latest: LeadRow[];
};

const busy = (d: Overview | null) => !!d && (!!d.stage.running || d.autopilot.running);

export default function OverviewPage() {
  const toast = useToast();
  const { data, refresh } = useApi<Overview>(() => api("/api/overview"), [], (d) => (busy(d) ? 3000 : null));
  const [pending, setPending] = useState<string | null>(null);

  const run = async (stage: string) => {
    setPending(stage);
    try {
      toast(await api<ActionResult>(`/api/actions/${stage}`, { method: "POST" }));
      await refresh();
    } catch (e) {
      toast((e as Error).message, false);
    } finally {
      setPending(null);
    }
  };

  if (!data) return <Spinner />;
  const { stats, targeting: t, autopilot: ap } = data;
  const totalLeads = Object.values(stats.leads).reduce((a, b) => a + b, 0);
  const done = data.setup.filter((s) => s.ok).length;
  const running = busy(data);

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle={
          <>
            Hunting <b className="text-slate-700">{t.seasons.join(" / ") || "internship"}</b> internships for {t.roles.join(", ")}
            {t.locations.length > 0 && <> in {t.locations.join(", ")}</>}.
          </>
        }
        actions={
          <Button variant="primary" icon={<Rocket className="size-4" />} loading={pending === "cycle"} disabled={running} onClick={() => run("cycle")}>
            Run full cycle
          </Button>
        }
      />

      {done < data.setup.length && (
        <Card className="mb-6" title={`Finish setup · ${done}/${data.setup.length}`} action={<div className="h-1.5 w-40 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-brand-500" style={{ width: `${(done / data.setup.length) * 100}%` }} /></div>}>
          <div className="grid gap-2 sm:grid-cols-2">
            {data.setup.map((s) => (
              <div key={s.name} className={cx("flex items-start gap-3 rounded-xl p-3", s.ok ? "bg-emerald-50/50" : "bg-slate-50")}>
                {s.ok ? <Check className="mt-0.5 size-4 text-emerald-600" /> : <Circle className="mt-0.5 size-4 text-slate-300" />}
                <div className="min-w-0">
                  <div className={cx("text-sm font-medium", s.ok ? "text-slate-500" : "text-slate-800")}>{s.name}</div>
                  {!s.ok &&
                    (s.href ? (
                      <Link to={s.href} className="text-xs text-brand-600 hover:underline">{s.how}</Link>
                    ) : (
                      <div className="text-xs text-slate-500">{s.how}</div>
                    ))}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-500">API keys are environment variables on the Render service (Dashboard → Environment).</p>
        </Card>
      )}

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={<Search />} label="Internship leads" value={totalLeads} tone="brand" />
        <Stat icon={<Users />} label="People with email" value={stats.contacts_with_email} sub={`of ${stats.contacts}`} tone="sky" />
        <Stat icon={<Mail />} label="Emails sent" value={stats.outreach["email:sent"] ?? 0} tone="violet" />
        <Stat icon={<MessageSquareReply />} label="Replies" value={stats.replies} tone="emerald" />
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card
          title={<span className="flex items-center gap-2"><Bot className="size-4 text-brand-600" /> Auto emailer</span>}
          action={<Chip tone={t.auto_send ? "green" : "gray"}>auto-send {t.auto_send ? "ON" : "OFF"}</Chip>}
        >
          {running && (
            <div className="mb-4 flex items-center gap-2 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-700">
              <RefreshCw className="size-4 animate-spin" />
              Running {data.stage.running ?? `autopilot: ${data.autopilot.step ?? "starting"}`}…
            </div>
          )}
          {!running && data.stage.result && <div className="mb-4 rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-600">Last run: {data.stage.result}</div>}
          <p className="text-sm leading-relaxed text-slate-600">
            Every <b>{t.cycle_every_hours}h</b> it finds new leads, finds who to email, crafts up to <b>{t.tailor_per_cycle}</b> tailored resumes and drafts emails.
            Each tick sends up to <b>{t.per_tick}</b> emails{t.followups_enabled && <> and one follow-up after <b>{t.followup_after_days} days</b> of silence</>}.
            {!t.auto_send && <> Auto-send is off, so drafts wait for you in <Link className="text-brand-600 hover:underline" to="/emails">Emails</Link>.</>}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button size="sm" icon={<Zap className="size-3.5" />} loading={pending === "tick"} disabled={running} onClick={() => run("tick")}>
              Tick now
            </Button>
            <Link to="/targeting"><Button size="sm" variant="ghost">Configure</Button></Link>
            <span className="ml-auto text-xs text-slate-500">Last cycle {ago(ap.last_cycle)} · last tick {ago(ap.last_tick)}</span>
          </div>
          {ap.history && ap.history.length > 0 && (
            <div className="mt-5 space-y-2 border-t border-slate-100 pt-4">
              <div className="text-xs font-medium tracking-wide text-slate-400 uppercase">Recent runs</div>
              {ap.history.slice(0, 4).map((h) => (
                <details key={h.at} className="group rounded-xl bg-slate-50 px-3 py-2">
                  <summary className="cursor-pointer text-xs font-medium text-slate-600">{when(h.at)}</summary>
                  <pre className="mt-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-slate-600">{h.lines.join("\n")}</pre>
                </details>
              ))}
            </div>
          )}
        </Card>

        <Card title="Sending budget">
          {data.allowance ? (
            data.allowance.paused_reason ? (
              <div className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">Paused: {data.allowance.paused_reason}</div>
            ) : (
              <>
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-semibold tracking-tight">{data.allowance.remaining}</span>
                  <span className="text-sm text-slate-500">of {data.allowance.cap} left today</span>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500" style={{ width: `${(data.allowance.sent_today / Math.max(1, data.allowance.cap)) * 100}%` }} />
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  Warm-up day {data.allowance.warmup_day} · bounce rate {(data.allowance.bounce_rate * 100).toFixed(1)}%
                </p>
              </>
            )
          ) : (
            <Empty icon={<Inbox className="size-5" />} title="Sending not configured">Set SMTP_* and SENDER_EMAIL on the server.</Empty>
          )}
          <Link to="/sending" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
            Deliverability & replies <ArrowRight className="size-4" />
          </Link>
        </Card>
      </div>

      <Card title="Step by step" className="mb-6">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["discover", "Find leads", "Apify searches"],
            ["enrich", "Find people", "Apollo / Hunter"],
            ["tailor", "Craft resumes", "10 at a time"],
            ["queue", "Draft emails", "one per person"],
            ["followups", "Follow-ups", "after silence"],
          ].map(([stage, title, sub], i) => (
            <button
              key={stage}
              disabled={running || pending !== null}
              onClick={() => run(stage)}
              className="group flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-left transition hover:border-brand-500 hover:bg-brand-50/40 disabled:opacity-50"
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-600 group-hover:bg-brand-600 group-hover:text-white">
                {pending === stage ? <RefreshCw className="size-4 animate-spin" /> : i + 1}
              </span>
              <span>
                <span className="block text-sm font-medium text-slate-800">{title}</span>
                <span className="block text-xs text-slate-500">{sub}</span>
              </span>
            </button>
          ))}
        </div>
      </Card>

      <Card title="Latest leads" action={<Link to="/leads" className="text-sm font-medium text-brand-600 hover:underline">View all</Link>}>
        {data.latest.length ? (
          <div className="divide-y divide-slate-100">
            {data.latest.map((l) => (
              <Link key={l.id} to={`/leads/${l.id}`} className="-mx-2 flex items-center justify-between gap-4 rounded-lg px-2 py-3 hover:bg-slate-50">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-slate-800">{l.title}</div>
                  <div className="truncate text-xs text-slate-500">
                    {l.company ?? l.poster_name ?? "unknown company"} {l.season && `· ${l.season}`} · {label(l.source)}
                  </div>
                </div>
                <StatusBadge status={l.status} />
              </Link>
            ))}
          </div>
        ) : (
          <Empty icon={<Play className="size-5" />} title="No leads yet">Set your targeting, then run a full cycle.</Empty>
        )}
      </Card>
    </>
  );
}

function Stat({ icon, label, value, sub, tone }: { icon: React.ReactNode; label: string; value: number; sub?: string; tone: "brand" | "sky" | "violet" | "emerald" }) {
  const t = { brand: "bg-brand-50 text-brand-600", sky: "bg-sky-50 text-sky-600", violet: "bg-violet-50 text-violet-600", emerald: "bg-emerald-50 text-emerald-600" }[tone];
  return (
    <div className="card p-5">
      <div className={cx("mb-4 grid size-9 place-items-center rounded-xl [&>svg]:size-[18px]", t)}>{icon}</div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold tracking-tight tabular-nums">{value}</span>
        {sub && <span className="text-xs text-slate-400">{sub}</span>}
      </div>
      <div className="mt-0.5 text-xs font-medium text-slate-500">{label}</div>
    </div>
  );
}
