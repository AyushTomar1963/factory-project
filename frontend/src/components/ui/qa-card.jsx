import { Card as ShadcnCard } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function Card({ children, className, padded = true, ...props }) {
  return (
    <ShadcnCard
      className={cn(
        "border-brand-100 rounded-2xl shadow-sm ring-brand-100/50",
        padded && "p-4",
        className,
      )}
      {...props}
    >
      {children}
    </ShadcnCard>
  )
}

export function Panel({ children, className }) {
  return (
    <div
      className={cn(
        "mx-auto w-full min-w-0 max-w-md overflow-hidden rounded-b-2xl border border-t-0 border-brand-100 bg-white p-4 shadow-[var(--shadow-card)] sm:p-8",
        className,
      )}
    >
      {children}
    </div>
  )
}
