import { Layers } from "lucide-react"
import { INSPECTION_STAGES } from "../../constants/inspection"
import { Field, FieldLabel } from "@/components/ui/field"
import { Select } from "../ui/FormField"

export function StageSelector({ stage, onChange, disabled }) {
  return (
    <Field className="mb-6">
      <FieldLabel className="flex items-center gap-2 text-xs font-bold text-gray-700">
        <Layers className="size-4 text-brand-600" />
        Inspection stage
      </FieldLabel>
      <Select
        value={stage}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="rounded-xl border-brand-100 font-medium disabled:opacity-60"
      >
        {INSPECTION_STAGES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </Select>
    </Field>
  )
}
