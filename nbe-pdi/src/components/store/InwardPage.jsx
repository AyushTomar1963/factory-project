import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Button } from "../ui/qa-button"
import { Input } from "../ui/FormField"
import { AlertBanner } from "../ui/StatusBadge"
import { fetchBinItem, submitInward } from "../../api/store"
import { StoreSectionCard } from "./StoreAppShell"
import { IssueMaterialForm } from "./IssueMaterialForm"

export function InwardPage({ token, binItemId, onIssueClick }) {
  const [details, setDetails] = useState(null)
  const [invoiceNo, setInvoiceNo] = useState("")
  const [invoiceDate, setInvoiceDate] = useState("")
  const [grnNo, setGrnNo] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [showIssue, setShowIssue] = useState(false)

  useEffect(() => {
    if (!binItemId) return
    let cancelled = false
    fetchBinItem(token, binItemId)
      .then((data) => {
        if (!cancelled) {
          setDetails(data)
          setInvoiceNo(data.invoice_no || "")
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [token, binItemId])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!binItemId || !invoiceNo.trim() || !invoiceDate) {
      toast.warning("Invoice number and date are required")
      return
    }
    setLoading(true)
    setError("")
    try {
      const data = await submitInward(token, binItemId, {
        invoice_no: invoiceNo.trim(),
        invoice_date: invoiceDate,
      })
      setGrnNo(data.grn_no)
      toast.success(`GRN ${data.grn_no} created`)
    } catch (err) {
      setError(err.message)
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!binItemId) {
    return (
      <StoreSectionCard title="Material inward">
        <p className="text-sm text-muted-foreground">
          Select an OK-bin item from the dashboard and click Start Inward.
        </p>
      </StoreSectionCard>
    )
  }

  return (
    <div className="space-y-6">
      <StoreSectionCard
        title="Inward lot details"
        description="Review lot information and create a GRN for OK-bin material."
        action={
          grnNo ? (
            <Button variant="muted" size="sm" onClick={() => setShowIssue(true)}>
              Issue Material
            </Button>
          ) : null
        }
      >
        {error && <AlertBanner variant="error" message={error} className="mb-4" />}
        {details && (
          <div className="mb-6 grid grid-cols-1 gap-3 rounded-lg border border-border bg-muted/30 p-4 text-sm sm:grid-cols-2">
            <p className="break-words"><strong>Part No:</strong> {details.part_no}</p>
            <p className="break-words"><strong>Supplier:</strong> {details.supplier}</p>
            <p><strong>Quantity:</strong> {details.quantity}</p>
            <p><strong>Bin status:</strong> {details.status}</p>
            <p><strong>Lot date:</strong> {details.lot_date ? new Date(details.lot_date).toLocaleString() : "—"}</p>
            <p><strong>IQC status:</strong> {details.iqc_lot?.overall_status || "—"}</p>
          </div>
        )}

        {grnNo ? (
          <div className="rounded-lg border border-green-200 bg-green-50 p-4">
            <p className="text-sm font-semibold text-green-800">GRN generated</p>
            <p className="mt-1 break-all font-mono text-lg font-bold text-green-900">{grnNo}</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <FieldGroup className="max-w-md gap-4">
              <Field>
                <FieldLabel htmlFor="invoice_no">Invoice No</FieldLabel>
                <Input
                  id="invoice_no"
                  value={invoiceNo}
                  onChange={(e) => setInvoiceNo(e.target.value)}
                  required
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="invoice_date">Invoice Date</FieldLabel>
                <Input
                  id="invoice_date"
                  type="date"
                  value={invoiceDate}
                  onChange={(e) => setInvoiceDate(e.target.value)}
                  required
                />
              </Field>
              <Button type="submit" variant="pass" disabled={loading}>
                {loading ? "Creating GRN…" : "OK — Create GRN"}
              </Button>
            </FieldGroup>
          </form>
        )}
      </StoreSectionCard>

      {(showIssue || grnNo) && (
        <IssueMaterialForm token={token} onDone={onIssueClick} />
      )}
    </div>
  )
}
