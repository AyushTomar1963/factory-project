import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ExternalLink, FileCheck2, Search } from "lucide-react";
import { api, type LeadRow } from "../api";
import { Card, Empty, label, PageHeader, ScoreBar, Spinner, StatusBadge, Tabs, useApi } from "../ui";

const TABS = ["all", "new", "enriched", "tailored", "queued", "contacted", "replied", "no_contact", "skipped"] as const;

export default function Leads() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "all";
  const source = params.get("source") ?? "all";
  const [q, setQ] = useState(params.get("q") ?? "");
  const nav = useNavigate();

  useEffect(() => {
    const t = setTimeout(() => setParam("q", q), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const setParam = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (!v || v === "all") next.delete(k);
    else next.set(k, v);
    setParams(next, { replace: true });
  };

  const qs = new URLSearchParams({ status, source, q: params.get("q") ?? "" }).toString();
  const { data } = useApi<{ leads: LeadRow[]; counts: Record<string, number>; sources: Record<string, string> }>(() => api(`/api/leads?${qs}`), [qs]);
  const total = data ? Object.values(data.counts).reduce((a, b) => a + b, 0) : 0;

  return (
    <>
      <PageHeader title="Internship leads" subtitle="People and companies taking interns. Each lead gets a tailored resume and a direct email; no application portals." />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs
          value={status}
          onChange={(v) => setParam("status", v)}
          items={TABS.map((t) => ({ value: t, label: label(t).replace(/^\w/, (c) => c.toUpperCase()), count: t === "all" ? total : data?.counts[t] ?? 0 }))}
        />
        <div className="flex gap-2">
          <select className="input w-auto" value={source} onChange={(e) => setParam("source", e.target.value)}>
            <option value="all">All sources</option>
            <option value="hiring_posts">Hiring posts</option>
            <option value="linkedin_jobs">LinkedIn listings</option>
            <option value="companies">My companies</option>
          </select>
          <div className="relative w-64">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
            <input className="input pl-9" placeholder="Search role, company, person" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>
      </div>

      <Card className="overflow-hidden p-0!">
        {!data ? (
          <Spinner />
        ) : data.leads.length === 0 ? (
          <Empty icon={<Search className="size-5" />} title="No leads in this view">Run discovery from the overview, or change the filters.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60 text-left text-xs font-medium tracking-wide text-slate-500 uppercase">
                  <th className="px-5 py-3">Opportunity</th>
                  <th className="px-3 py-3">Season</th>
                  <th className="px-3 py-3">Fit</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Found</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.leads.map((l) => (
                  <tr key={l.id} onClick={() => nav(`/leads/${l.id}`)} className="cursor-pointer transition hover:bg-slate-50">
                    <td className="max-w-md px-5 py-3.5">
                      <Link to={`/leads/${l.id}`} className="block truncate font-medium text-slate-800">{l.title}</Link>
                      <div className="truncate text-xs text-slate-500">
                        {l.company ?? "company unknown"}
                        {l.poster_name && ` · posted by ${l.poster_name}`} · {label(l.source)}
                        {l.location && ` · ${l.location}`}
                      </div>
                    </td>
                    <td className="px-3 py-3.5 text-xs whitespace-nowrap text-slate-600">{l.season ?? "—"}</td>
                    <td className="px-3 py-3.5"><ScoreBar score={l.match_score} /></td>
                    <td className="px-3 py-3.5">
                      <div className="flex items-center gap-1.5">
                        <StatusBadge status={l.status} />
                        {l.doc_id && <FileCheck2 className="size-4 text-emerald-500" aria-label="resume crafted" />}
                      </div>
                    </td>
                    <td className="px-3 py-3.5 text-xs whitespace-nowrap text-slate-500">{l.discovered_at.slice(0, 10)}</td>
                    <td className="px-5 py-3.5 text-right">
                      {l.url && (
                        <a href={l.url} target="_blank" rel="noopener" onClick={(e) => e.stopPropagation()} className="text-slate-400 hover:text-brand-600">
                          <ExternalLink className="size-4" />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
