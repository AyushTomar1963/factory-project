import { cn } from "@/lib/utils"

const VARIANTS = {
  primary:
    "bg-brand-600 hover:bg-brand-700 text-white shadow-sm disabled:opacity-50",
  gradient:
    "bg-gradient-to-r from-brand-700 to-indigo-700 hover:from-brand-800 hover:to-indigo-800 text-white shadow-lg shadow-brand-200 hover:-translate-y-0.5 active:scale-[0.99]",
  pass: "bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-700 hover:to-green-700 text-white shadow-lg shadow-green-100 hover:-translate-y-0.5 active:scale-[0.99]",
  hold: "bg-gradient-to-r from-amber-400 to-yellow-400 hover:from-amber-500 hover:to-yellow-500 text-slate-900 shadow-lg shadow-amber-100 hover:-translate-y-0.5 active:scale-[0.99]",
  fail: "bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700 text-white shadow-lg shadow-red-100 hover:-translate-y-0.5 active:scale-[0.99]",
  danger: "bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700 text-white",
  warning: "bg-yellow-500 hover:bg-yellow-600 text-gray-900",
  ghost: "bg-white/10 backdrop-blur text-white border border-white/20 hover:bg-white/20",
  muted: "bg-gray-300 hover:bg-gray-400 text-gray-800",
  mutedLight: "bg-gray-200 hover:bg-gray-300 text-gray-800",
  scan: "bg-gradient-to-r from-brand-700 to-indigo-700 hover:from-brand-800 hover:to-indigo-800 text-white font-black py-5 text-xl shadow-lg shadow-brand-200 hover:-translate-y-0.5 active:scale-[0.99]",
}

const SIZES = {
  sm: "px-4 py-2 text-sm rounded-lg",
  md: "px-4 py-3 text-sm rounded-xl",
  lg: "py-5 rounded-2xl text-sm font-black",
  block: "w-full py-3 rounded-lg font-bold",
}

export function QaButton({
  variant = "primary",
  size = "md",
  className,
  children,
  ...props
}) {
  return (
    <button
      type="button"
      className={cn(
        "font-bold transition-all duration-300 disabled:opacity-50 disabled:pointer-events-none",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

export { QaButton as Button }
