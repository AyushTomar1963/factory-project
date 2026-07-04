import { cn } from "@/lib/utils"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

/**
 * Horizontally scrollable table shell — required for wide data on mobile.
 * Wraps content in touch-friendly swipe scrolling without breaking the viewport.
 */
export function ScrollTable({ children, className, label = "Scrollable data table" }) {
  return (
    <div
      className={cn(
        "w-full max-w-full overflow-x-auto rounded-lg border border-border",
        "[-webkit-overflow-scrolling:touch]",
        className,
      )}
      role="region"
      aria-label={label}
      tabIndex={0}
    >
      <div className="min-w-max">{children}</div>
    </div>
  )
}

/** Reusable truncated cell for long dynamic text */
export function TableText({ children, className, mono = false }) {
  return (
    <span
      className={cn(
        "block max-w-[12rem] truncate sm:max-w-[16rem]",
        mono && "font-mono text-xs",
        className,
      )}
      title={typeof children === "string" ? children : undefined}
    >
      {children}
    </span>
  )
}

export { Table, TableBody, TableCell, TableHead, TableHeader, TableRow }
