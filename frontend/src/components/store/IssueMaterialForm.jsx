import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "../ui/qa-button"
import { Input, Textarea } from "../ui/FormField"
import { AlertBanner } from "../ui/StatusBadge"
import { fetchGrns, submitIssue } from "../../api/store"
import { StoreSectionCard } from "./StoreAppShell"

export function IssueMaterialForm({ token, onDone }) {
  const [grns, setGrns] = useState([])
  const [grnId, setGrnId] = useState("")
  const [partFilter, setPartFilter] = useState("")
  const [quantity, setQuantity] = useState("")
  const [issuedTo, setIssuedTo] = useState("")
  const [remarks, setRemarks] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    let cancelled = false
    fetchGrns(token, partFilter.trim() || undefined)
      .then((data) => {
        if (!cancelled) setGrns(data.grns || [])
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [token, partFilter])

  const selectedGrn = grns.find((grn) => String(grn.id) === grnId)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!grnId || !quantity || !issuedTo.trim()) {
      toast.warning("GRN, quantity, and issued-to are required")
      return
    }
    setLoading(true)
    setError("")
    try {
      const data = await submitIssue(token, {
        grn_id: Number(grnId),
        quantity_issued: Number(quantity),
        issued_to: issuedTo.trim(),
        remarks: remarks.trim() || null,
      })
      toast.success(`Issue ${data.issue_no} created`)
      setQuantity("")
      setIssuedTo("")
      setRemarks("")
      onDone?.()
    } catch (err) {
      setError(err.message)
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <StoreSectionCard
      title="Issue material"
      description="Issue material against an inwarded GRN."
    >
      {error && <AlertBanner variant="error" message={error} className="mb-4" />}

      <form onSubmit={handleSubmit}>
        <FieldGroup className="max-w-xl gap-4">
          <Field>
            <FieldLabel htmlFor="part_filter">Search part no</FieldLabel>
            <Input
              id="part_filter"
              placeholder="Filter GRNs by part number"
              value={partFilter}
              onChange={(e) => setPartFilter(e.target.value)}
            />
          </Field>

          <Field>
            <FieldLabel>GRN / Part</FieldLabel>
            <Select value={grnId} onValueChange={setGrnId}>
              <SelectTrigger className="min-h-11 w-full">
                <SelectValue placeholder="Select GRN" />
              </SelectTrigger>
              <SelectContent>
                {grns.map((grn) => (
                  <SelectItem key={grn.id} value={String(grn.id)}>
                    {grn.grn_no} — {grn.part_no} (remaining: {grn.remaining_quantity})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          {selectedGrn && (
            <p className="text-sm text-muted-foreground">
              Available quantity: <strong>{selectedGrn.remaining_quantity}</strong>
            </p>
          )}

          <Field>
            <FieldLabel htmlFor="quantity">Quantity issued</FieldLabel>
            <Input
              id="quantity"
              type="number"
              min="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="issued_to">Issued to</FieldLabel>
            <Input
              id="issued_to"
              value={issuedTo}
              onChange={(e) => setIssuedTo(e.target.value)}
              required
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="remarks">Remarks</FieldLabel>
            <Textarea
              id="remarks"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
            />
          </Field>

          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? "Issuing…" : "Issue material"}
          </Button>
        </FieldGroup>
      </form>
    </StoreSectionCard>
  )
}
