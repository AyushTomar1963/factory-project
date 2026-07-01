import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { STATUS_BADGE_STYLES } from "@/constants/inspection"
import { cn } from "@/lib/utils"

const ALERT_TONES = {
  info: "border-brand-200 bg-brand-50 text-brand-800",
  error: "border-red-200 bg-red-50 text-red-700",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
}

export function StatusBadge({ status, className }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-full px-3 py-1 text-xs font-bold",
        STATUS_BADGE_STYLES[status] || "bg-gray-100 text-gray-700",
        className,
      )}
    >
      {status || "N/A"}
    </Badge>
  )
}

export function AlertBanner({ children, tone = "info", className }) {
  return (
    <Alert className={cn("font-bold text-center", ALERT_TONES[tone], className)}>
      <AlertDescription className="text-inherit">{children}</AlertDescription>
    </Alert>
  )
}

export function LoadingScreen({ message = "Loading..." }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-gray-100 p-6">
      <Skeleton className="h-4 w-48" />
      <p className="text-sm font-bold text-gray-500">{message}</p>
    </div>
  )
}
