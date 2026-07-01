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
        "w-full max-w-md bg-white rounded-b-2xl shadow-[var(--shadow-card)] p-8 border border-brand-100 border-t-0",
        className,
      )}
    >
      {children}
    </div>
  )
}
