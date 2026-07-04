import { useState } from "react"
import { Download } from "lucide-react"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
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
import { Button } from "../ui/qa-button"
import { Input } from "../ui/FormField"
import { AlertBanner } from "../ui/StatusBadge"
import { exportReport, fetchIqcReport, fetchStoreReport } from "../../api/reports"
import { StoreSectionCard } from "./StoreAppShell"

function ReportTable({ rows, emptyMessage, showBin = false }) {
  return (
    <ScrollTable label="Report detail rows">
      <Table className="min-w-[640px]">
        <TableHeader>
          <TableRow>
            <TableHead className="whitespace-nowrap">Part No</TableHead>
            <TableHead className="whitespace-nowrap">Date</TableHead>
            <TableHead className="whitespace-nowrap">{showBin ? "Status / Bin" : "Status"}</TableHead>
            <TableHead className="whitespace-nowrap">Quantity</TableHead>
            <TableHead className="whitespace-nowrap">Failed qty</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-muted-foreground">
                {emptyMessage}
              </TableCell>
            </TableRow>
          ) : (
            rows.map((row, idx) => (
              <TableRow key={`${row.part_no}-${row.date}-${idx}`}>
                <TableCell>
                  <TableText mono>{row.part_no}</TableText>
                </TableCell>
                <TableCell className="whitespace-nowrap">{row.date}</TableCell>
                <TableCell className="whitespace-nowrap">{row.status || row.bin_type}</TableCell>
                <TableCell className="whitespace-nowrap">
                  {row.lot_quantity ?? row.quantity}
                </TableCell>
                <TableCell className="whitespace-nowrap">{row.failed_quantity ?? 0}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </ScrollTable>
  )
}

function SummaryTable({ summary }) {
  return (
    <ScrollTable label="Report summary">
      <Table className="min-w-[480px]">
        <TableHeader>
          <TableRow>
            <TableHead className="whitespace-nowrap">Part No</TableHead>
            <TableHead className="whitespace-nowrap">Date</TableHead>
            <TableHead className="whitespace-nowrap">Failure count</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {summary.length === 0 ? (
            <TableRow>
              <TableCell colSpan={3} className="text-muted-foreground">
                Run a report to see summary data.
              </TableCell>
            </TableRow>
          ) : (
            summary.map((row) => (
              <TableRow key={`${row.part_no}-${row.date}`}>
                <TableCell>
                  <TableText mono>{row.part_no}</TableText>
                </TableCell>
                <TableCell className="whitespace-nowrap">{row.date}</TableCell>
                <TableCell className="whitespace-nowrap">{row.failure_count}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </ScrollTable>
  )
}

export function ReportsPanel({ token, defaultType = "store" }) {
  const [reportType, setReportType] = useState(defaultType)
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [partNo, setPartNo] = useState("")
  const [rows, setRows] = useState([])
  const [summary, setSummary] = useState([])
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState("")

  const filters = {
    ...(startDate && { start_date: startDate }),
    ...(endDate && { end_date: endDate }),
    ...(partNo.trim() && { part_no: partNo.trim() }),
  }

  const loadReport = async () => {
    setLoading(true)
    setError("")
    try {
      const data =
        reportType === "iqc"
          ? await fetchIqcReport(token, filters)
          : await fetchStoreReport(token, filters)
      setRows(data.rows || [])
      setSummary(data.summary || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async (format) => {
    setExporting(true)
    try {
      await exportReport(token, { type: reportType, format, ...filters })
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <StoreSectionCard
      title="Reports"
      description="Filter IQC and store activity, then export CSV or Excel."
      action={
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Button
            variant="muted"
            size="sm"
            className="w-full sm:w-auto"
            disabled={exporting}
            onClick={() => handleExport("csv")}
          >
            <Download className="size-4" />
            Export CSV
          </Button>
          <Button
            variant="primary"
            size="sm"
            className="w-full sm:w-auto"
            disabled={exporting}
            onClick={() => handleExport("xlsx")}
          >
            <Download className="size-4" />
            Export Excel
          </Button>
        </div>
      }
    >
      {error && <AlertBanner variant="error" message={error} className="mb-4" />}

      <Tabs value={reportType} onValueChange={setReportType}>
        <TabsList className="tabs-scroll mb-4 flex w-full gap-1">
          <TabsTrigger value="store" className="min-h-11 shrink-0 px-4">
            Store report
          </TabsTrigger>
          <TabsTrigger value="iqc" className="min-h-11 shrink-0 px-4">
            IQC report
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <FieldGroup className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field>
          <FieldLabel htmlFor="start_date">Start date</FieldLabel>
          <Input
            id="start_date"
            type="date"
            className="min-h-11"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="end_date">End date</FieldLabel>
          <Input
            id="end_date"
            type="date"
            className="min-h-11"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </Field>
        <Field className="sm:col-span-2 lg:col-span-1">
          <FieldLabel htmlFor="part_no">Part no</FieldLabel>
          <Input
            id="part_no"
            className="min-h-11"
            value={partNo}
            onChange={(e) => setPartNo(e.target.value)}
            placeholder="PN-1001"
          />
        </Field>
        <div className="flex items-end sm:col-span-2 lg:col-span-1">
          <Button
            variant="primary"
            size="block"
            className="w-full"
            onClick={loadReport}
            disabled={loading}
          >
            {loading ? "Loading…" : "Run report"}
          </Button>
        </div>
      </FieldGroup>

      <div className="space-y-6">
        <div className="min-w-0">
          <h3 className="mb-2 text-sm font-bold text-foreground">Summary</h3>
          <SummaryTable summary={summary} />
        </div>

        <div className="min-w-0">
          <h3 className="mb-2 text-sm font-bold text-foreground">Detail rows</h3>
          <ReportTable rows={rows} emptyMessage="No detail rows loaded." showBin />
        </div>
      </div>
    </StoreSectionCard>
  )
}
