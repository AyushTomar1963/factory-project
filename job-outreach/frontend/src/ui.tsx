import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import type { ActionResult } from "./api";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------- buttons

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "success";
  size?: "sm" | "md";
  loading?: boolean;
  icon?: ReactNode;
};

export function Button({ variant = "secondary", size = "md", loading, icon, className, children, disabled, ...rest }: BtnProps) {
  const styles = {
    primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm shadow-brand-600/20",
    secondary: "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:border-slate-300",
    ghost: "text-slate-600 hover:bg-slate-100",
    danger: "bg-white text-rose-600 border border-rose-200 hover:bg-rose-50",
    success: "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm shadow-emerald-600/20",
  }[variant];
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm",
        styles,
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

// ---------------------------------------------------------------- badges

const STATUS_COLORS: Record<string, string> = {
  new: "bg-slate-100 text-slate-700",
  enriched: "bg-sky-50 text-sky-700 ring-sky-200",
  tailored: "bg-amber-50 text-amber-700 ring-amber-200",
  queued: "bg-violet-50 text-violet-700 ring-violet-200",
  contacted: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  replied: "bg-emerald-600 text-white ring-emerald-600",
  no_contact: "bg-slate-100 text-slate-500",
  skipped: "bg-slate-100 text-slate-400",
  draft: "bg-amber-50 text-amber-700 ring-amber-200",
  approved: "bg-brand-50 text-brand-700 ring-brand-100",
  sent: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  done: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  rejected: "bg-slate-100 text-slate-500",
  bounced: "bg-rose-50 text-rose-700 ring-rose-200",
  failed: "bg-rose-50 text-rose-700 ring-rose-200",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={cx("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-transparent ring-inset", STATUS_COLORS[status] ?? "bg-slate-100 text-slate-700")}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function Chip({ children, tone = "brand" }: { children: ReactNode; tone?: "brand" | "red" | "gray" | "green" }) {
  const t = {
    brand: "bg-brand-50 text-brand-700",
    red: "bg-rose-50 text-rose-700",
    gray: "bg-slate-100 text-slate-600",
    green: "bg-emerald-50 text-emerald-700",
  }[tone];
  return <span className={cx("inline-flex items-center rounded-lg px-2 py-0.5 text-xs font-medium", t)}>{children}</span>;
}

// ---------------------------------------------------------------- layout bits

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, action, children, className }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("card p-5", className)}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-sm font-semibold text-slate-900">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icon && <div className="mb-3 rounded-2xl bg-slate-100 p-3 text-slate-400">{icon}</div>}
      <p className="font-medium text-slate-700">{title}</p>
      {children && <div className="mt-1 max-w-sm text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
      <Loader2 className="size-5 animate-spin text-brand-500" /> {label ?? "Loading…"}
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { value: T; label: string; count?: number }[] }) {
  return (
    <div className="flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1">
      {items.map((it) => (
        <button
          key={it.value}
          onClick={() => onChange(it.value)}
          className={cx(
            "rounded-lg px-3 py-1.5 text-xs font-medium transition",
            value === it.value ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800",
          )}
        >
          {it.label}
          {it.count !== undefined && <span className="ml-1.5 text-slate-400">{it.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; hint?: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 py-2">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cx("relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition", checked ? "bg-brand-600" : "bg-slate-300")}
      >
        <span className={cx("absolute top-0.5 size-4 rounded-full bg-white shadow transition-all", checked ? "left-[18px]" : "left-0.5")} />
      </button>
      <span>
        <span className="block text-sm font-medium text-slate-800">{label}</span>
        {hint && <span className="block text-xs text-slate-500">{hint}</span>}
      </span>
    </label>
  );
}

export function ScoreBar({ score }: { score?: number | null }) {
  if (score === null || score === undefined) return <span className="text-xs text-slate-400">n/a</span>;
  const pct = Math.round(score * 100);
  return (
    <div className="w-20">
      <div className="text-xs font-semibold tabular-nums text-slate-700">{pct}%</div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export const when = (s?: string | null) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "never");
export const ago = (s?: string | null) => {
  if (!s) return "never";
  const d = (Date.now() - new Date(s).getTime()) / 1000;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
};
export const label = (s: string) => s.replace(/_/g, " ");

// ---------------------------------------------------------------- toasts

type Toast = { id: number; ok: boolean; text: string };
const ToastCtx = createContext<(r: ActionResult | string, ok?: boolean) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const push = useCallback((r: ActionResult | string, ok = true) => {
    const t = typeof r === "string" ? { ok, text: r } : { ok: r.ok, text: r.message };
    const id = next.current++;
    setToasts((xs) => [...xs, { id, ...t }]);
    setTimeout(() => setToasts((xs) => xs.filter((x) => x.id !== id)), 5000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3.5 text-sm shadow-lg shadow-slate-900/5">
            {t.ok ? <CheckCircle2 className="size-5 shrink-0 text-emerald-500" /> : <XCircle className="size-5 shrink-0 text-rose-500" />}
            <span className="text-slate-700">{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

// ---------------------------------------------------------------- data hook

export function useApi<T>(load: () => Promise<T>, deps: unknown[] = [], pollMs?: (data: T | null) => number | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadRef = useRef(load);
  loadRef.current = load;
  const pollRef = useRef(pollMs);
  pollRef.current = pollMs;
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const alive = useRef(true);

  // Every refresh re-evaluates polling, so starting a background job from a
  // button (then calling refresh) begins polling until the job finishes.
  const refresh = useCallback(async (): Promise<T | null> => {
    clearTimeout(timer.current);
    let d: T | null = null;
    try {
      d = await loadRef.current();
      setData(d);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
    const ms = pollRef.current?.(d);
    if (alive.current && ms) timer.current = setTimeout(refresh, ms);
    return d;
  }, []);

  useEffect(() => {
    alive.current = true;
    refresh();
    return () => {
      alive.current = false;
      clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, refresh, setData };
}
