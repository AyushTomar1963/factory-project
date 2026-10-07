import { useEffect, useState } from "react"
import { RefreshCw } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
import { AlertBanner } from "../ui/StatusBadge"
import { fetchStoreBins, fetchStoreSummary, syncIqcToStore } from "../../api/store"
import { BIN_TABS } from "../../constants/store"
import { StoreSectionCard } from "./StoreAppShell"

function SummaryStrip({ summary }) {
  if (!summary) return null

  const pendingSync = summary.iqc_pending_sync || 0
  const okPending = summary.bin_pending_inward?.OK || 0

  return (
    <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          IQC lots linked
        </p>
        <p className="mt-1 text-2xl font-black text-foreground">
          {summary.iqc_lots_total || 0}
          <span className="ml-2 text-sm font-medium text-muted-foreground">
            / {summary.iqc_logs_total || 0} inspections
          </span>
        </p>
      </div>
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          OK bin pending inward
        </p>
        <p className="mt-1 text-2xl font-black text-brand-700">{okPending}</p>
      </div>
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Awaiting IQC sync
        </p>
        <p className="mt-1 text-2xl font-black text-amber-700">{pendingSync}</p>
      </div>
    </div>
  )
}

export function BinDashboard({ token, onStartInward }) {
  const [activeBin, setActiveBin] = useState("ok")
  const [items, setItems] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState("")
  const [info, setInfo] = useState("")
  const [reloadKey, setReloadKey] = useState(0)

  const handleBinChange = (value) => {
    setActiveBin(value)
    setLoading(true)
    setError("")
    setItems([])
  }

  useEffect(() => {
    let cancelled = false

    Promise.all([fetchStoreBins(token, activeBin), fetchStoreSummary(token)])
      .then(([binsData, summaryData]) => {
        if (cancelled) return
        setItems(binsData.items || [])
        setSummary(summaryData)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [token, activeBin, reloadKey])

  const handleSync = async () => {
    setSyncing(true)
    setError("")
    setInfo("")
    try {
      const result = await syncIqcToStore(token)
      setInfo(
        result.message +
          (result.synced_lots
            ? ` (${result.synced_lots} lots, ${result.bin_items_created} bin items)`
            : ""),
      )
      setReloadKey((key) => key + 1)
    } catch (err) {
      setError(err.message)
    } finally {
      setSyncing(false)
    }
  }

  const pendingSync = summary?.iqc_pending_sync || 0

  return (
    <StoreSectionCard
      title="Bin inventory"
      description="Lots routed automatically from IQC inspection into OK, Rejected, or Doubtful bins."
      action={
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Button
            variant="muted"
            className="w-full sm:w-auto"
            onClick={() => {
              setLoading(true)
              setError("")
              setReloadKey((key) => key + 1)
            }}
            disabled={loading}
          >
            <RefreshCw className="size-4" />
            Refresh
          </Button>
          {pendingSync > 0 && (
            <Button
              variant="primary"
              className="w-full sm:w-auto"
              onClick={handleSync}
              disabled={syncing}
            >
              {syncing ? "Syncing IQC…" : `Sync ${pendingSync} IQC lot(s)`}
            </Button>
          )}
        </div>
      }
    >
      {error && (
        <AlertBanner tone="error" className="mb-4">
          {error}
        </AlertBanner>
      )}
      {info && (
        <AlertBanner tone="info" className="mb-4">
          {info}
        </AlertBanner>
      )}
      {pendingSync > 0 && (
        <AlertBanner tone="warning" className="mb-4">
          {`${pendingSync} finalized IQC inspection(s) are waiting to enter store bins. Tap "Sync IQC lot(s)" to import them now.`}
        </AlertBanner>
      )}

      <SummaryStrip summary={summary} />

      <Tabs value={activeBin} onValueChange={handleBinChange}>
        <TabsList className="tabs-scroll mb-4 flex w-full gap-1">
          {BIN_TABS.map((tab) => (
            <TabsTrigger
              key={tab.id}
              value={tab.id}
              className="min-h-11 shrink-0 px-4"
            >
              {tab.label}
              {summary?.bin_totals?.[tab.binType] != null && (
                <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-[10px] font-bold">
                  {summary.bin_totals[tab.binType]}
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>

        {BIN_TABS.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="min-w-0">
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading bin items…</p>
            ) : items.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-center">
                <p className="text-sm font-medium text-foreground">No items in this bin.</p>
                <p className="mt-2 text-xs text-muted-foreground break-words">
                  Items appear here after IQC workers finalize inspections. Each lot is
                  split into OK, Rejected, or Doubtful bins based on inspection ratings.
                </p>
              </div>
            ) : (
              <ScrollTable label={`${tab.label} bin inventory`}>
                <Table className="min-w-[720px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="whitespace-nowrap">Supplier</TableHead>
                      <TableHead className="whitespace-nowrap">Date</TableHead>
                      <TableHead className="whitespace-nowrap">Invoice No</TableHead>
                      <TableHead className="whitespace-nowrap">Part No</TableHead>
                      <TableHead className="whitespace-nowrap">Qty</TableHead>
                      <TableHead className="whitespace-nowrap">Status</TableHead>
                      {tab.id === "ok" && (
                        <TableHead className="whitespace-nowrap text-right">Action</TableHead>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <TableText>{item.supplier}</TableText>
                        </TableCell>
                        <TableCell className="whitespace-nowrap">
                          {item.lot_date
                            ? new Date(item.lot_date).toLocaleDateString()
                            : "—"}
                        </TableCell>
                        <TableCell>
                          <TableText mono>{item.invoice_no || "—"}</TableText>
                        </TableCell>
                        <TableCell>
                          <TableText mono>{item.part_no}</TableText>
                        </TableCell>
                        <TableCell className="whitespace-nowrap">{item.quantity}</TableCell>
                        <TableCell className="whitespace-nowrap">{item.status}</TableCell>
                        {tab.id === "ok" && (
                          <TableCell className="text-right">
                            {item.status === "PENDING" ? (
                              <Button
                                variant="primary"
                                className="w-full min-w-[8.5rem] sm:w-auto"
                                onClick={() => onStartInward(item.id)}
                              >
                                Start Inward
                              </Button>
                            ) : (
                              <span className="text-xs text-muted-foreground break-words">
                                {item.grn_no || "Inwarded"}
                              </span>
                            )}
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </ScrollTable>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </StoreSectionCard>
  )
}
