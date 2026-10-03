import {
  AlertTriangle,
  BarChart3,
  ClipboardList,
  TrendingUp,
} from "lucide-react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  ScrollTable,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableText,
} from "@/components/ui/scroll-table"
import { StatusBadge } from "../ui/StatusBadge"
import { cn } from "@/lib/utils"

const failureChartConfig = {
  failures: {
    label: "Failures",
    color: "var(--color-fail)",
  },
}

export function StatCard({ title, value, subtitle, accent, icon: Icon, valueClassName }) {
  return (
    <Card
      className={cn(
        "group border-border border-t-4 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md",
        accent,
      )}
    >
      <CardContent className="p-5">
        <div className="mb-2 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="mb-1 text-sm font-semibold text-muted-foreground">{title}</p>
            <p className={valueClassName || "text-3xl font-black tracking-tight text-foreground"}>
              {value}
            </p>
          </div>
          {Icon && (
            <div className="rounded-lg bg-muted p-2 text-muted-foreground group-hover:bg-brand-50 group-hover:text-brand-600">
              <Icon className="size-5" />
            </div>
          )}
        </div>
        {subtitle && (
          <p className="text-xs font-medium text-muted-foreground">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  )
}

export function FailureHeatmapCard({ stageFailures }) {
  const chartData = ["Stage 1", "Stage 2", "Stage 3"].map((stage) => ({
    stage: stage.replace("Stage ", "S"),
    failures: stageFailures?.[stage] || 0,
  }))

  return (
    <Card className="border-border border-t-4 border-t-indigo-500 shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-muted-foreground">
            Failure heatmap
          </CardTitle>
          <BarChart3 className="size-5 text-indigo-600" />
        </div>
        <CardDescription>Defects by assembly stage</CardDescription>
      </CardHeader>
      <CardContent className="pb-4">
        <ChartContainer config={failureChartConfig} className="aspect-auto h-[140px] w-full">
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="stage" tickLine={false} axisLine={false} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar
              dataKey="failures"
              fill="var(--color-failures)"
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}

export function InspectionLogsTable({ logs }) {
  const rows = logs ? [...logs].reverse() : []

  if (rows.length === 0) {
    return (
      <Card className="border-border shadow-sm">
        <CardHeader className="border-b border-border bg-muted/30">
          <CardTitle className="text-lg font-bold">Recent inspection logs</CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <Empty className="border-none">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <ClipboardList />
              </EmptyMedia>
              <EmptyTitle>No inspections yet</EmptyTitle>
              <EmptyDescription>
                Logs from worker stations will appear here after the first submission.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="overflow-hidden border-border shadow-sm">
      <CardHeader className="border-b border-border bg-muted/30">
        <CardTitle className="text-lg font-bold">Recent inspection logs</CardTitle>
        <CardDescription>{rows.length} records loaded</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <div className="max-h-[min(28rem,60vh)] overflow-y-auto">
          <ScrollTable label="Recent inspection logs">
            <Table className="min-w-[960px]">
              <TableHeader className="sticky top-0 z-10 bg-background shadow-sm">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="whitespace-nowrap">Time</TableHead>
                  <TableHead className="whitespace-nowrap">Part</TableHead>
                  <TableHead className="whitespace-nowrap">Stage</TableHead>
                  <TableHead className="whitespace-nowrap">Supplier</TableHead>
                  <TableHead className="whitespace-nowrap">Invoice</TableHead>
                  <TableHead className="whitespace-nowrap">Lot</TableHead>
                  <TableHead className="whitespace-nowrap">Freq%</TableHead>
                  <TableHead className="whitespace-nowrap">Worker</TableHead>
                  <TableHead className="whitespace-nowrap">Status</TableHead>
                  <TableHead className="whitespace-nowrap">AI category</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((log, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {log.Timestamp || "N/A"}
                    </TableCell>
                    <TableCell>
                      <TableText>{log["Part Name"] || "N/A"}</TableText>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{log.Stage || "N/A"}</TableCell>
                    <TableCell>
                      <TableText>{log.Supplier || "-"}</TableText>
                    </TableCell>
                    <TableCell>
                      <TableText mono>{log.Invoice_Number || "-"}</TableText>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{log.Lot_Quantity || "-"}</TableCell>
                    <TableCell className="whitespace-nowrap">
                      {log.Checking_Frequency ? `${log.Checking_Frequency}%` : "-"}
                    </TableCell>
                    <TableCell>
                      <TableText>{log["Logged By"] || "Unknown"}</TableText>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={log.Status} />
                    </TableCell>
                    <TableCell>
                      <TableText>{log["AI Category"] || "-"}</TableText>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollTable>
        </div>
      </CardContent>
    </Card>
  )
}

export const STAT_ICONS = {
  total: ClipboardList,
  yield: TrendingUp,
  defect: AlertTriangle,
}
