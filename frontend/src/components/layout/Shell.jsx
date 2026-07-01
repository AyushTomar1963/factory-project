import { cn } from "../../lib/cn"

export function BrandLogo({ size = "md", className }) {
  const sizes = {
    sm: "h-10",
    md: "h-12",
    lg: "h-16",
  }
  return (
    <img
      src="/logo.jpg"
      alt="Rushab Industries Logo"
      className={cn(sizes[size], "object-contain", className)}
    />
  )
}

export function PageHeader({ eyebrow, title, subtitle, onLogout, compact }) {
  return (
    <div
      className={cn(
        "w-full overflow-hidden rounded-t-2xl bg-gradient-to-r from-brand-700 to-indigo-700 px-6 py-4 shadow-lg shadow-brand-200 flex items-center justify-between text-white",
        !compact && "max-w-md",
      )}
    >
      <div>
        {eyebrow && (
          <p className="text-xs uppercase tracking-[0.28em] text-brand-100/90 font-semibold">
            {eyebrow}
          </p>
        )}
        <h2 className={cn("font-black", compact ? "text-lg" : "text-3xl")}>
          {title}
        </h2>
        {subtitle && (
          <p className="text-sm font-bold text-brand-100 mt-1">{subtitle}</p>
        )}
      </div>
      {onLogout && (
        <button
          type="button"
          onClick={onLogout}
          className="rounded-lg border border-white/30 bg-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/20 transition-colors"
        >
          Sign out
        </button>
      )}
    </div>
  )
}

export function WorkerShell({ header, children }) {
  return (
    <div className="flex min-h-screen flex-col items-center p-6">
      {header}
      {children}
    </div>
  )
}

export function AdminShell({ children }) {
  return (
    <div className="min-h-screen p-6">
      <div className="mx-auto max-w-6xl space-y-6">{children}</div>
    </div>
  )
}
