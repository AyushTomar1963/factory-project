import { useEffect, useState } from "react"
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
import { fetchStoreBins } from "../../api/store"
import { BIN_TABS } from "../../constants/store"
import { StoreSectionCard } from "./StoreAppShell"

export function BinDashboard({ token, onStartInward }) {
  const [activeBin, setActiveBin] = useState("ok")
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const handleBinChange = (value) => {
    setActiveBin(value)
    setLoading(true)
    setError("")
    setItems([])
  }

  useEffect(() => {
    let cancelled = false
    fetchStoreBins(token, activeBin)
      .then((data) => {
        if (!cancelled) setItems(data.items || [])
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
  }, [token, activeBin])

  return (
    <StoreSectionCard
      title="Bin inventory"
      description="Lots routed from IQC inspection into OK, Rejected, or Doubtful bins."
    >
      {error && <AlertBanner variant="error" message={error} className="mb-4" />}

      <Tabs value={activeBin} onValueChange={handleBinChange}>
        <TabsList className="tabs-scroll mb-4 flex w-full gap-1">
          {BIN_TABS.map((tab) => (
            <TabsTrigger
              key={tab.id}
              value={tab.id}
              className="min-h-11 shrink-0 px-4"
            >
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {BIN_TABS.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="min-w-0">
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading bin items…</p>
            ) : items.length === 0 ? (
              <p className="text-sm text-muted-foreground">No items in this bin.</p>
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
