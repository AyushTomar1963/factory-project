import { Input as ShadcnInput } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea as ShadcnTextarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

const FIELD_CLASS =
  "h-auto min-h-10 border-2 border-gray-300 rounded-lg px-3 py-2.5 text-sm focus-visible:border-brand-500 focus-visible:ring-brand-100"

export function FormField({ label, htmlFor, children, className }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      {label && (
        <Label
          htmlFor={htmlFor}
          className="text-xs font-bold text-gray-700"
        >
          {label}
        </Label>
      )}
      {children}
    </div>
  )
}

export function Input({ className, mono, ...props }) {
  return (
    <ShadcnInput
      className={cn(FIELD_CLASS, mono && "font-mono", className)}
      {...props}
    />
  )
}

export function Select({ className, children, ...props }) {
  return (
    <select className={cn(FIELD_CLASS, "bg-white", className)} {...props}>
      {children}
    </select>
  )
}

export function Textarea({ className, ...props }) {
  return (
    <ShadcnTextarea
      className={cn(
        "min-h-24 rounded-2xl border-2 border-gray-300 p-4 text-base shadow-sm focus-visible:border-brand-500 focus-visible:ring-brand-100",
        className,
      )}
      {...props}
    />
  )
}
