import { useEffect, useState, type FormEvent } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { FileText, Inbox, LayoutDashboard, Loader2, LogOut, Mail, Menu, Search, Send, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { api, auth, ApiError } from "./api";
import { Button, cx } from "./ui";
import Overview from "./pages/Overview";
import Leads from "./pages/Leads";
import LeadDetail from "./pages/LeadDetail";
import Emails from "./pages/Emails";
import ResumePage from "./pages/Resume";
import Targeting from "./pages/Targeting";
import Sending from "./pages/Sending";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/resume", label: "Resume crafter", icon: FileText },
  { to: "/targeting", label: "Targeting & autopilot", icon: SlidersHorizontal },
  { to: "/leads", label: "Internship leads", icon: Search },
  { to: "/emails", label: "Emails", icon: Mail },
  { to: "/sending", label: "Sending & replies", icon: Send },
];

type AuthState = "checking" | "ok" | "login";

export default function App() {
  const [state, setState] = useState<AuthState>("checking");
  const [waking, setWaking] = useState(false);
  const [menu, setMenu] = useState(false);
  const loc = useLocation();

  useEffect(() => setMenu(false), [loc.pathname]);

  useEffect(() => {
    const onUnauth = () => setState("login");
    const onWaking = () => setWaking(true);
    const onAwake = () => setWaking(false);
    window.addEventListener("jobhunt:unauthorized", onUnauth);
    window.addEventListener("jobhunt:waking", onWaking);
    window.addEventListener("jobhunt:awake", onAwake);
    api("/api/me")
      .then(() => setState("ok"))
      .catch((e) => setState(e instanceof ApiError && e.status === 401 ? "login" : "ok"));
    return () => {
      window.removeEventListener("jobhunt:unauthorized", onUnauth);
      window.removeEventListener("jobhunt:waking", onWaking);
      window.removeEventListener("jobhunt:awake", onAwake);
    };
  }, []);

  if (state === "checking") return <Splash waking={waking} />;
  if (state === "login") return <Login onDone={() => setState("ok")} waking={waking} />;

  return (
    <div className="min-h-full lg:grid lg:grid-cols-[260px_1fr]">
      <aside
        className={cx(
          "fixed inset-y-0 left-0 z-40 flex w-[260px] flex-col bg-slate-950 px-4 py-6 text-slate-300 transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0",
          menu ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="mb-8 flex items-center justify-between px-2">
          <Logo />
          <button className="text-slate-400 lg:hidden" onClick={() => setMenu(false)}>
            <X className="size-5" />
          </button>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cx(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                  isActive ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-slate-100",
                )
              }
            >
              <Icon className="size-[18px]" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs leading-relaxed text-slate-400">
          <Sparkles className="mb-1 size-4 text-brand-500" />
          Winter &amp; summer internships. Straight to people's inboxes, no portals.
        </div>
        {auth.get() && (
          <button
            onClick={() => {
              auth.clear();
              setState("login");
            }}
            className="mt-3 flex items-center gap-2 px-3 py-2 text-xs text-slate-500 hover:text-slate-200"
          >
            <LogOut className="size-4" /> Sign out
          </button>
        )}
      </aside>
      {menu && <div className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" onClick={() => setMenu(false)} />}

      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur lg:hidden">
          <button onClick={() => setMenu(true)} className="text-slate-600">
            <Menu className="size-5" />
          </button>
          <Logo dark />
        </header>
        {waking && (
          <div className="flex items-center justify-center gap-2 bg-amber-50 px-4 py-2 text-sm text-amber-800">
            <Loader2 className="size-4 animate-spin" /> Waking up the server (free tier naps when idle). This can take up to a minute…
          </div>
        )}
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/resume" element={<ResumePage />} />
            <Route path="/targeting" element={<Targeting />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/leads/:id" element={<LeadDetail />} />
            <Route path="/emails" element={<Emails />} />
            <Route path="/sending" element={<Sending />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function Logo({ dark }: { dark?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-violet-600 text-sm font-bold text-white shadow-lg shadow-brand-600/30">
        j
      </div>
      <span className={cx("text-lg font-semibold tracking-tight", dark ? "text-slate-900" : "text-white")}>
        job<span className="text-brand-500">hunt</span>
      </span>
    </div>
  );
}

function Splash({ waking }: { waking: boolean }) {
  return (
    <div className="grid h-full place-items-center bg-slate-950">
      <div className="flex flex-col items-center gap-4 text-slate-400">
        <Logo />
        <Loader2 className="size-5 animate-spin text-brand-500" />
        {waking && <p className="text-sm">Waking up the server, hang tight…</p>}
      </div>
    </div>
  );
}

function Login({ onDone, waking }: { onDone: () => void; waking: boolean }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    auth.set(pw);
    try {
      await api("/api/me");
      onDone();
    } catch (ex) {
      auth.clear();
      setErr(ex instanceof ApiError && ex.status === 401 ? "Wrong password" : (ex as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="relative grid h-full place-items-center overflow-hidden bg-slate-950 px-4">
      <div className="pointer-events-none absolute -top-40 left-1/2 size-[600px] -translate-x-1/2 rounded-full bg-brand-600/30 blur-[120px]" />
      <form onSubmit={submit} className="relative w-full max-w-sm rounded-3xl border border-white/10 bg-white/[0.04] p-8 shadow-2xl backdrop-blur">
        <Logo />
        <h1 className="mt-6 text-xl font-semibold text-white">Welcome back</h1>
        <p className="mt-1 text-sm text-slate-400">Enter your dashboard password to continue.</p>
        <input
          type="password"
          autoFocus
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          placeholder="Password"
          className="mt-6 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-brand-500 focus:ring-4 focus:ring-brand-500/20"
        />
        {err && <p className="mt-2 text-sm text-rose-400">{err}</p>}
        {waking && <p className="mt-2 text-sm text-amber-300">Waking up the server…</p>}
        <Button variant="primary" className="mt-5 w-full py-3" loading={busy} disabled={!pw}>
          Sign in
        </Button>
        <p className="mt-6 flex items-center gap-2 text-xs text-slate-500">
          <Inbox className="size-4" /> Internship outreach, on autopilot.
        </p>
      </form>
    </div>
  );
}
