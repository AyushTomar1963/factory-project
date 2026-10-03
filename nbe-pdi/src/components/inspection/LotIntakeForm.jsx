import { ClipboardList, Pencil } from "lucide-react"
import { CHECKING_FREQUENCIES } from "../../constants/inspection"
import {
  Field,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Button } from "../ui/qa-button"
import { Card } from "../ui/qa-card"
import { Input, Select } from "../ui/FormField"

export function LotIntakeForm({ intake, suppliers, onChange, onSubmit, onError }) {
  const handleSubmit = () => {
    const error = onSubmit()
    if (error) onError?.(error)
  }

  return (
    <Card className="mb-6 border-2 border-brand-100 p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="mb-4 flex items-center gap-2">
        <ClipboardList className="size-5 text-brand-600" />
        <h2 className="text-lg font-black text-gray-800">Lot intake details</h2>
      </div>
      <FieldGroup className="gap-4">
        <Field>
          <FieldLabel>Supplier</FieldLabel>
          <Select value={intake.supplier} onChange={(e) => onChange("supplier", e.target.value)}>
            <option value="">Select supplier…</option>
            {suppliers.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        </Field>
        <Field>
          <FieldLabel>Invoice number</FieldLabel>
          <Input
            type="text"
            placeholder="e.g. INV-2024-00123"
            value={intake.invoiceNumber}
            onChange={(e) => onChange("invoiceNumber", e.target.value)}
            className="font-mono"
          />
        </Field>
        <Field>
          <FieldLabel>Lot quantity</FieldLabel>
          <Input
            type="number"
            placeholder="e.g. 500"
            value={intake.lotQuantity}
            onChange={(e) => onChange("lotQuantity", e.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel>Checking frequency (%)</FieldLabel>
          <Select
            value={intake.checkingFrequency}
            onChange={(e) => onChange("checkingFrequency", e.target.value)}
          >
            <option value="">Select frequency…</option>
            {CHECKING_FREQUENCIES.map((f) => (
              <option key={f} value={f}>
                {f}%
              </option>
            ))}
          </Select>
        </Field>
      </FieldGroup>
      <Button variant="gradient" size="block" className="mt-5" onClick={handleSubmit}>
        Confirm &amp; proceed to inspection
      </Button>
    </Card>
  )
}

export function LotIntakeSummary({ intake, onEdit }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-3 rounded-xl border border-brand-200 bg-brand-50 p-4">
      <div className="space-y-1 text-xs text-gray-700">
        <p>
          <span className="font-bold">Supplier:</span> {intake.supplier}
        </p>
        <p>
          <span className="font-bold">Invoice:</span>{" "}
          <span className="font-mono">{intake.invoiceNumber}</span>
          <span className="mx-1 text-gray-400">|</span>
          <span className="font-bold">Lot:</span> {intake.lotQuantity} pcs
          <span className="mx-1 text-gray-400">|</span>
          <span className="font-bold">Freq:</span> {intake.checkingFrequency}%
        </p>
      </div>
      <button
        type="button"
        onClick={onEdit}
        className="flex shrink-0 items-center gap-1 text-xs font-bold text-brand-600 hover:text-brand-700"
      >
        <Pencil className="size-3.5" />
        Edit
      </button>
    </div>
  )
}
