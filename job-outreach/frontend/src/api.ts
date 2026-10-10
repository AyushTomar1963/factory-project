// All calls go to same-origin /api, which Vercel rewrites to the Render backend.
// The browser never makes a cross-origin request, so CORS never applies.
// Set VITE_API_BASE to call a backend URL directly instead (the backend allows *.vercel.app).
const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";
const TOKEN_KEY = "jobhunt_token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export const auth = {
  get: () => localStorage.getItem(TOKEN_KEY) ?? "",
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

type Opts = { method?: string; json?: unknown; form?: FormData; signal?: AbortSignal };

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function emit(name: string, detail?: unknown) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

async function raw(path: string, opts: Opts = {}): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = auth.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  // The free Render instance sleeps; the first request after a nap can take ~50s
  // and the proxy may answer 502/504 meanwhile, so retry for a while.
  for (let attempt = 0; ; attempt++) {
    let res: Response | null = null;
    try {
      res = await fetch(`${BASE}${path}`, { method: opts.method ?? "GET", headers, body, signal: opts.signal });
    } catch (e) {
      if ((e as Error).name === "AbortError") throw e;
    }
    if (res && ![502, 503, 504].includes(res.status)) {
      emit("jobhunt:awake");
      if (res.status === 401) {
        emit("jobhunt:unauthorized");
        throw new ApiError(401, "Password required");
      }
      if (!res.ok) {
        let msg = res.statusText;
        try {
          const j = await res.json();
          msg = j.detail ?? j.error ?? j.message ?? msg;
        } catch {
          /* not json */
        }
        throw new ApiError(res.status, String(msg));
      }
      return res;
    }
    if (attempt >= 12) throw new ApiError(res?.status ?? 0, "The server is not responding. Try again in a minute.");
    emit("jobhunt:waking");
    await sleep(5000);
  }
}

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const res = await raw(path, opts);
  return res.json() as Promise<T>;
}

/** Fetch an authenticated file and return an object URL (caller revokes it). */
export async function blobUrl(path: string, signal?: AbortSignal) {
  const res = await raw(path, { signal });
  return URL.createObjectURL(await res.blob());
}

/** Fetch an authenticated file (PDF/HTML) and open it in a new tab. */
export async function openFile(path: string) {
  const win = window.open("", "_blank"); // opened synchronously so popup blockers allow it
  try {
    const res = await raw(path);
    const url = URL.createObjectURL(await res.blob());
    if (win) win.location.href = url;
    else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (e) {
    win?.close();
    throw e;
  }
}

// ---------------------------------------------------------------- types

export type SetupItem = { name: string; ok: boolean; how: string; href?: string };
export type Targeting = {
  seasons: string[];
  roles: string[];
  locations: string[];
  companies: string[];
  sources: string[];
  max_results_per_query: number;
  require_season: boolean;
  auto_send: boolean;
  cycle_every_hours: number;
  per_tick: number;
  tailor_per_cycle: number;
  followups_enabled: boolean;
  followup_after_days: number;
};
export type Allowance = {
  cap: number;
  sent_today: number;
  remaining: number;
  warmup_day: number;
  bounce_rate: number;
  paused_reason: string | null;
};
export type RunStatus = {
  stage: { running: string | null; result: string | null };
  autopilot: { running: boolean; started: string | null; step: string | null };
  send: { running: boolean; started: string | null; log: string[]; summary: string | null };
};
export type AutopilotState = {
  last_cycle?: string;
  last_tick?: string;
  history?: { at: string; lines: string[] }[];
};
export type LeadRow = {
  id: number;
  source: string;
  company: string | null;
  domain?: string | null;
  title: string;
  location?: string | null;
  url?: string | null;
  season: string | null;
  poster_name: string | null;
  match_score?: number | null;
  status: string;
  discovered_at: string;
  doc_id?: number | null;
};
export type Contact = {
  id: number;
  name: string;
  title: string | null;
  email: string | null;
  email_confidence: number | null;
  linkedin_url: string | null;
  source: string;
};
export type OutreachRow = {
  id: number;
  lead_id: number;
  channel: string;
  kind: string;
  status: string;
  subject: string | null;
  body: string;
  error: string | null;
  sent_at: string | null;
  replied_at: string | null;
  name: string;
  contact_title: string | null;
  email: string | null;
  linkedin_url: string | null;
  email_confidence: number | null;
  contact_source: string;
  lead_title: string;
  company: string | null;
  season: string | null;
  lead_source: string;
};
export type ActionResult = { ok: boolean; message: string };
