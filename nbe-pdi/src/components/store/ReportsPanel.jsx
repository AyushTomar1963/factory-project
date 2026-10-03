import { useEffect, useState } from "react"
import { Download, Plus, Trash2 } from "lucide-react"
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
import {
  exportReport,
  fetchBprReport,
  fetchIqcReport,
  fetchIssueReport,
  fetchStoreReport,
} from "../../api/reports"
import { deleteBuffer, fetchBuffers, saveBuffer } from "../../api/store"
import { StoreSectionCard } from "./StoreAppShell"

const REPORT_TABS = [
  { id: "store", label: "Store report" },
  { id: "iqc", label: "IQC report" },
  { id: "issue", label: "Issue report" },
  { id: "bpr", label: "BPR" },
]

const BPR_STATUS_STYLES = {
  Green: "bg-green-100 text-green-700",
  Yellow: "bg-amber-100 text-amber-800",
  Red: "bg-red-100 text-red-700",
}

function StatusPill({ status }) {
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold ${
        BPR_STATUS_STYLES[status] || "bg-gray-100 text-gray-700"
      }`}
    >
      {status}
    </span>
  )
}

function QaReportTable({ rows, emptyMessage }) {
  return (
    <ScrollTable label="Report detail rows">
      <Table className="min-w-[640px]">
        <TableHeader>
          <TableRow>
            <TableHead className="whitespace-nowrap">Part No</TableHead>
            <TableHead className="whitespace-nowrap">Date</TableHead>
            <TableHead className="whitespace-nowrap">Status / Bin</TableHead>
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
                <TableCell className="whitespace-nowrap">
                  {row.status || row.bin_type}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {row.lot_quantity ?? row.quantity}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {row.failed_quantity ?? 0}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </ScrollTable>
  )
}

function QaSummaryTable({ summary }) {
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

function IssueReportTable({ rows }) {
  return (
    <ScrollTable label="Issue report rows">
      <Table className="min-w-[760px]">
        <TableHeader>
          <TableRow>
            <TableHead className="whitespace-nowrap">Issue No</TableHead>
            <TableHead className="whitespace-nowrap">GRN No</TableHead>
            <TableHead className="whitespace-nowrap">Part No</TableHead>
            <TableHead className="whitespace-nowrap">Qty issued</TableHead>
            <TableHead className="whitespace-nowrap">Issued to</TableHead>
            <TableHead className="whitespace-nowrap">Date</TableHead>
            <TableHead className="whitespace-nowrap">Remarks</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-muted-foreground">
                No material issues for the selected filters.
              </TableCell>
            </TableRow>
          ) : (
            rows.map((row, idx) => (
              <TableRow key={`${row.issue_no}-${idx}`}>
                <TableCell>
                  <TableText mono>{row.issue_no}</TableText>
                </TableCell>
                <TableCell>
                  <TableText mono>{row.grn_no || "—"}</TableText>
                </TableCell>
                <TableCell>
                  <TableText mono>{row.part_no}</TableText>
                </TableCell>
                <TableCell className="whitespace-nowrap">{row.quantity_issued}</TableCell>
                <TableCell>
                  <TableText>{row.issued_to}</TableText>
                </TableCell>
                <TableCell className="whitespace-nowrap">{row.date}</TableCell>
                <TableCell>
                  <TableText>{row.remarks || "—"}</TableText>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </ScrollTable>
  )
}

function IssueSummaryTable({ summary, totalIssued }) {
  return (
    <ScrollTable label="Issue report summary">
      <Table className="min-w-[420px]">
        <TableHeader>
          <TableRow>
            <TableHead className="whitespace-nowrap">Part No</TableHead>
            <TableHead className="whitespace-nowrap">Issues</TableHead>
            <TableHead className="whitespace-nowrap">Total issued</TableHead>
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
            <>
              {summary.map((row) => (
                <TableRow key={row.part_no}>
                  <TableCell>
                    <TableText mono>{row.part_no}</TableText>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{row.issue_count}</TableCell>
                  <TableCell className="whitespace-nowrap">{row.total_issued}</TableCell>
                </TableRow>
              ))}
              <TableRow className="font-bold">
                <TableCell>Total</TableCell>
                <TableCell />
                <TableCell className="whitespace-nowrap">{totalIssued}</TableCell>
              </TableRow>
            </>
          )}
        </TableBody>
      </Table>
    </ScrollTable>
  )
}

function BprReportTable({ rows }) {
  return (
    <ScrollTable label="Buffer penetration report">
      <Table className="min-w-[900px]">
        <TableHeader>
          <TableRow>
            <TableHead className="whitespace-nowrap">Material Code</TableHead>
            <TableHead className="whitespace-nowrap">Description</TableHead>
            <TableHead className="whitespace-nowrap">Warehouse</TableHead>
            <TableHead className="whitespace-nowrap">Min</TableHead>
            <TableHead className="whitespace-nowrap">Max</TableHead>
            <TableHead className="whitespace-nowrap">Current</TableHead>
            <TableHead className="whitespace-nowrap">Penetration %</TableHead>
            <TableHead className="whitespace-nowrap">Status</TableHead>
            <TableHead className="whitespace-nowrap">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={9} className="text-muted-foreground">
                No buffer materials configured. Add materials below to build the report.
              </TableCell>
            </TableRow>
          ) : (
            rows.map((row) => (
              <TableRow key={row.material_code}>
                <TableCell>
                  <TableText mono>{row.material_code}</TableText>
                </TableCell>
                <TableCell>
                  <TableText>{row.material_description || "—"}</TableText>
                </TableCell>
                <TableCell className="whitespace-nowrap">{row.warehouse}</TableCell>
                <TableCell className="whitespace-nowrap">{row.min_buffer}</TableCell>
                <TableCell className="whitespace-nowrap">{row.max_buffer}</TableCell>
                <TableCell className="whitespace-nowrap">{row.current_stock}</TableCell>
                <TableCell className="whitespace-nowrap font-semibold">
                  {row.penetration_pct}%
                </TableCell>
                <TableCell>
                  <StatusPill status={row.status} />
                </TableCell>
                <TableCell className="whitespace-nowrap">{row.action_required}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </ScrollTable>
  )
}

function BufferManager({ token, onSaved }) {
  const [buffers, setBuffers] = useState([])
  const [form, setForm] = useState({
    material_code: "",
    material_description: "",
    warehouse: "WH-01",
    min_buffer: "",
    max_buffer: "",
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    fetchBuffers(token)
      .then((data) => {
        if (!cancelled) setBuffers(data.buffers || [])
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [token, reloadKey])

  const setField = (field, value) =>
    setForm((prev) => ({ ...prev, [field]: value }))

  const handleSave = async (e) => {
    e.preventDefault()
    if (!form.material_code.trim()) return
    setSaving(true)
    setError("")
    try {
      await saveBuffer(token, {
        material_code: form.material_code.trim(),
        material_description: form.material_description.trim() || null,
        warehouse: form.warehouse.trim() || "WH-01",
        min_buffer: Number(form.min_buffer) || 0,
        max_buffer: Number(form.max_buffer) || 0,
      })
      setForm({
        material_code: "",
        material_description: "",
        warehouse: form.warehouse,
        min_buffer: "",
        max_buffer: "",
      })
      setReloadKey((key) => key + 1)
      onSaved?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (bufferId) => {
    setError("")
    try {
      await deleteBuffer(token, bufferId)
      setReloadKey((key) => key + 1)
      onSaved?.()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4">
      <h3 className="mb-1 text-sm font-bold text-foreground">Buffer configuration</h3>
      <p className="mb-4 text-xs text-muted-foreground">
        Set min &amp; max buffer per material. Current stock is calculated from inwarded
        GRNs minus issued material.
      </p>

      {error && (
        <AlertBanner tone="error" className="mb-4">
          {error}
        </AlertBanner>
      )}

      <form onSubmit={handleSave}>
        <FieldGroup className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <Field className="lg:col-span-1">
            <FieldLabel htmlFor="buf_code">Material code</FieldLabel>
            <Input
              id="buf_code"
              className="min-h-11"
              value={form.material_code}
              onChange={(e) => setField("material_code", e.target.value)}
              placeholder="P001"
            />
          </Field>
          <Field className="sm:col-span-2 lg:col-span-2">
            <FieldLabel htmlFor="buf_desc">Description</FieldLabel>
            <Input
              id="buf_desc"
              className="min-h-11"
              value={form.material_description}
              onChange={(e) => setField("material_description", e.target.value)}
              placeholder="1 HP Pump"
            />
          </Field>
          <Field className="lg:col-span-1">
            <FieldLabel htmlFor="buf_wh">Warehouse</FieldLabel>
            <Input
              id="buf_wh"
              className="min-h-11"
              value={form.warehouse}
              onChange={(e) => setField("warehouse", e.target.value)}
              placeholder="WH-01"
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="buf_min">Min buffer</FieldLabel>
            <Input
              id="buf_min"
              type="number"
              min="0"
              className="min-h-11"
              value={form.min_buffer}
              onChange={(e) => setField("min_buffer", e.target.value)}
              placeholder="100"
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="buf_max">Max buffer</FieldLabel>
            <Input
              id="buf_max"
              type="number"
              min="0"
              className="min-h-11"
              value={form.max_buffer}
              onChange={(e) => setField("max_buffer", e.target.value)}
              placeholder="500"
            />
          </Field>
        </FieldGroup>
        <Button type="submit" variant="primary" disabled={saving} className="w-full sm:w-auto">
          <Plus className="size-4" />
          {saving ? "Saving…" : "Save material"}
        </Button>
      </form>

      {buffers.length > 0 && (
        <div className="mt-4">
          <ScrollTable label="Configured buffer materials">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="whitespace-nowrap">Code</TableHead>
                  <TableHead className="whitespace-nowrap">Description</TableHead>
                  <TableHead className="whitespace-nowrap">Warehouse</TableHead>
                  <TableHead className="whitespace-nowrap">Min</TableHead>
                  <TableHead className="whitespace-nowrap">Max</TableHead>
                  <TableHead className="whitespace-nowrap text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {buffers.map((buf) => (
                  <TableRow key={buf.id}>
                    <TableCell>
                      <TableText mono>{buf.material_code}</TableText>
                    </TableCell>
                    <TableCell>
                      <TableText>{buf.material_description || "—"}</TableText>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{buf.warehouse}</TableCell>
                    <TableCell className="whitespace-nowrap">{buf.min_buffer}</TableCell>
                    <TableCell className="whitespace-nowrap">{buf.max_buffer}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="muted"
                        size="sm"
                        className="min-h-11"
                        onClick={() => handleDelete(buf.id)}
                        aria-label={`Delete ${buf.material_code}`}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollTable>
        </div>
      )}
    </div>
  )
}

export function ReportsPanel({ token, defaultType = "store" }) {
  const [reportType, setReportType] = useState(defaultType)
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [partNo, setPartNo] = useState("")
  const [warehouse, setWarehouse] = useState("")
  const [rows, setRows] = useState([])
  const [summary, setSummary] = useState([])
  const [statusCounts, setStatusCounts] = useState(null)
  const [totalIssued, setTotalIssued] = useState(0)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState("")

  const isBpr = reportType === "bpr"
  const isIssue = reportType === "issue"

  const buildFilters = () =>
    isBpr
      ? {
          ...(warehouse.trim() && { warehouse: warehouse.trim() }),
          ...(partNo.trim() && { part_no: partNo.trim() }),
        }
      : {
          ...(startDate && { start_date: startDate }),
          ...(endDate && { end_date: endDate }),
          ...(partNo.trim() && { part_no: partNo.trim() }),
        }

  const handleTabChange = (value) => {
    setReportType(value)
    setRows([])
    setSummary([])
    setStatusCounts(null)
    setTotalIssued(0)
    setError("")
  }

  const loadReport = async () => {
    setLoading(true)
    setError("")
    try {
      const filters = buildFilters()
      let data
      if (reportType === "iqc") data = await fetchIqcReport(token, filters)
      else if (reportType === "store") data = await fetchStoreReport(token, filters)
      else if (reportType === "issue") data = await fetchIssueReport(token, filters)
      else data = await fetchBprReport(token, filters)

      setRows(data.rows || [])
      setSummary(data.summary || [])
      setStatusCounts(data.status_counts || null)
      setTotalIssued(data.total_issued || 0)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async (format) => {
    setExporting(true)
    setError("")
    try {
      await exportReport(token, { type: reportType, format, ...buildFilters() })
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <StoreSectionCard
      title="Reports"
      description="Filter IQC, store, issue and buffer activity, then export CSV or Excel."
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
      {error && (
        <AlertBanner tone="error" className="mb-4">
          {error}
        </AlertBanner>
      )}

      <Tabs value={reportType} onValueChange={handleTabChange}>
        <TabsList className="tabs-scroll mb-4 flex w-full gap-1">
          {REPORT_TABS.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id} className="min-h-11 shrink-0 px-4">
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <FieldGroup className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isBpr ? (
          <Field>
            <FieldLabel htmlFor="warehouse">Warehouse</FieldLabel>
            <Input
              id="warehouse"
              className="min-h-11"
              value={warehouse}
              onChange={(e) => setWarehouse(e.target.value)}
              placeholder="WH-01"
            />
          </Field>
        ) : (
          <>
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
          </>
        )}
        <Field className={isBpr ? "" : "sm:col-span-2 lg:col-span-1"}>
          <FieldLabel htmlFor="part_no">{isBpr ? "Material code" : "Part no"}</FieldLabel>
          <Input
            id="part_no"
            className="min-h-11"
            value={partNo}
            onChange={(e) => setPartNo(e.target.value)}
            placeholder={isBpr ? "P001" : "PN-1001"}
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

      {isBpr ? (
        <div className="space-y-6">
          {statusCounts && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {["Green", "Yellow", "Red"].map((status) => (
                <div key={status} className="rounded-lg border border-border bg-muted/30 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {status}
                  </p>
                  <p className="mt-1 text-2xl font-black text-foreground">
                    {statusCounts[status] || 0}
                    <span className="ml-2 text-sm font-medium text-muted-foreground">
                      material(s)
                    </span>
                  </p>
                </div>
              ))}
            </div>
          )}

          <div className="min-w-0">
            <h3 className="mb-2 text-sm font-bold text-foreground">
              Buffer penetration report
            </h3>
            <BprReportTable rows={rows} />
          </div>

          <BufferManager token={token} onSaved={loadReport} />
        </div>
      ) : isIssue ? (
        <div className="space-y-6">
          <div className="min-w-0">
            <h3 className="mb-2 text-sm font-bold text-foreground">Summary by part</h3>
            <IssueSummaryTable summary={summary} totalIssued={totalIssued} />
          </div>
          <div className="min-w-0">
            <h3 className="mb-2 text-sm font-bold text-foreground">Issue detail rows</h3>
            <IssueReportTable rows={rows} />
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="min-w-0">
            <h3 className="mb-2 text-sm font-bold text-foreground">Summary</h3>
            <QaSummaryTable summary={summary} />
          </div>
          <div className="min-w-0">
            <h3 className="mb-2 text-sm font-bold text-foreground">Detail rows</h3>
            <QaReportTable rows={rows} emptyMessage="No detail rows loaded." />
          </div>
        </div>
      )}
    </StoreSectionCard>
  )
}
