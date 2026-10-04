import { useState } from "react"
import { ScrollTable } from "@/components/ui/scroll-table"
import { PDI_SECTIONS, pdiTemplateParameters, isPdiTemplateParameter } from "../../pdi"
import { Button } from "../ui/qa-button"
import { FormField, Input } from "../ui/FormField"
import { PartQrButton } from "./PartQrLabel"

const TEMPLATE_PARAMETERS = pdiTemplateParameters()

function TemplateChecks({ selected, onChange }) {
  const selectedSet = new Set(selected)
  const toggle = (parameter) => {
    if (selectedSet.has(parameter)) onChange(selected.filter((name) => name !== parameter))
    else onChange([...selected, parameter])
  }

  const allSelected = selected.length === TEMPLATE_PARAMETERS.length
  const summary = allSelected
    ? `Full pre-dispatch template is already on this part (${selected.length} checks). Open only to remove a line.`
    : selected.length === 0
      ? "No pre-dispatch lines selected. Open to put the template on this part."
      : `${selected.length} of ${TEMPLATE_PARAMETERS.length} pre-dispatch checks. Open to change the lines.`

  return (
    <details className="rounded-lg border border-brand-100 bg-brand-50/40">
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-brand-900">
        {summary}
      </summary>
      <div className="max-h-80 space-y-4 overflow-y-auto border-t border-brand-100 px-4 py-3">
        {!allSelected && (
          <button
            type="button"
            className="text-xs font-bold text-brand-700 hover:underline"
            onClick={() => onChange(TEMPLATE_PARAMETERS)}
          >
            Select every pre-dispatch line
          </button>
        )}
        {PDI_SECTIONS.map((section) => (
          <div key={section.title}>
            <p className="text-xs font-bold uppercase tracking-wide text-brand-800">{section.title}</p>
            <ul className="mt-1 space-y-1">
              {section.items.map((item) => (
                <li key={item.parameter}>
                  <label className="flex items-start gap-2 text-sm text-gray-800">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={selectedSet.has(item.parameter)}
                      onChange={() => toggle(item.parameter)}
                    />
                    <span>
                      {item.parameter}
                      {item.specification ? (
                        <span className="block text-xs text-gray-500">{item.specification}</span>
                      ) : null}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </details>
  )
}

export function ParameterEditor({ parameters, onChange, allowEmpty = false }) {
  const [draft, setDraft] = useState("")

  const addParameter = () => {
    const trimmed = draft.trim()
    if (!trimmed || isPdiTemplateParameter(trimmed)) {
      setDraft("")
      return
    }
    if (parameters.some((p) => p.toLowerCase() === trimmed.toLowerCase())) {
      setDraft("")
      return
    }
    onChange([...parameters, trimmed])
    setDraft("")
  }

  const removeParameter = (index) => {
    onChange(parameters.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      <FormField label="Inspection parameters">
        <p className="text-xs text-gray-500 mb-2">
          Extra part-specific checks only. The pre-dispatch template is already included.
        </p>
        <div className="flex gap-2">
          <Input
            type="text"
            placeholder="e.g. Outer Diameter (OD)"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                addParameter()
              }
            }}
          />
          <Button type="button" variant="primary" size="sm" onClick={addParameter}>
            Add
          </Button>
        </div>
      </FormField>
      {parameters.length > 0 ? (
        <ul className="flex flex-wrap gap-2">
          {parameters.map((param, index) => (
            <li
              key={`${param}-${index}`}
              className="inline-flex items-center gap-2 bg-brand-50 border border-brand-200 rounded-lg px-3 py-1.5 text-sm font-semibold text-brand-800"
            >
              {param}
              <button
                type="button"
                onClick={() => removeParameter(index)}
                className="text-red-500 hover:text-red-700 font-bold"
                aria-label={`Remove ${param}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : allowEmpty ? null : (
        <p className="text-sm text-amber-700 font-semibold bg-amber-50 border border-amber-200 rounded-lg p-3">
          Add at least one parameter before saving.
        </p>
      )}
    </div>
  )
}

export function ProductForm({ initial, onSubmit, onCancel, isSaving }) {
  const isEdit = Boolean(initial?.part_number)
  const starting = initial?.parameters || []
  const [partNumber, setPartNumber] = useState(initial?.part_number || "")
  const [partName, setPartName] = useState(initial?.part_name || "")
  const [groupName, setGroupName] = useState(initial?.group || "")
  const [templateChecks, setTemplateChecks] = useState(
    isEdit ? starting.filter((name) => isPdiTemplateParameter(name)) : TEMPLATE_PARAMETERS,
  )
  const [extras, setExtras] = useState(starting.filter((name) => !isPdiTemplateParameter(name)))
  const [error, setError] = useState("")

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")
    if (!isEdit && !partNumber.trim()) {
      setError("Part number is required.")
      return
    }
    if (!partName.trim()) {
      setError("Part name is required.")
      return
    }
    const parameters = [
      ...TEMPLATE_PARAMETERS.filter((name) => templateChecks.includes(name)),
      ...extras.filter((name) => !isPdiTemplateParameter(name)),
    ]
    if (parameters.length === 0) {
      setError("Keep at least one pre-dispatch check.")
      return
    }
    try {
      await onSubmit({
        part_number: partNumber.trim().toUpperCase(),
        part_name: partName.trim(),
        group_name: groupName.trim() || null,
        parameters,
      })
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField label="Part number" htmlFor="part-number">
          <Input
            id="part-number"
            value={partNumber}
            onChange={(e) => setPartNumber(e.target.value.toUpperCase())}
            placeholder="e.g. BSH-01"
            mono
            disabled={isEdit}
            required
          />
        </FormField>
        <FormField label="Part name" htmlFor="part-name">
          <Input
            id="part-name"
            value={partName}
            onChange={(e) => setPartName(e.target.value)}
            placeholder="e.g. Bush Housing"
            required
          />
        </FormField>
      </div>
      <FormField label="Product group (optional)" htmlFor="group-name">
        <Input
          id="group-name"
          value={groupName}
          onChange={(e) => setGroupName(e.target.value)}
          placeholder="e.g. Bushings, Rotors"
        />
      </FormField>
      <TemplateChecks selected={templateChecks} onChange={setTemplateChecks} />
      <ParameterEditor parameters={extras} onChange={setExtras} allowEmpty />
      {error && (
        <p className="text-sm font-bold text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          {error}
        </p>
      )}
      <div className="flex gap-3 pt-2">
        <Button type="submit" variant="gradient" size="sm" disabled={isSaving}>
          {isSaving ? "Saving..." : isEdit ? "Update product" : "Create product"}
        </Button>
        {onCancel && (
          <Button type="button" variant="muted" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}

function ProductChecks({ parameters = [] }) {
  const templateCount = parameters.filter((name) => isPdiTemplateParameter(name)).length
  const extras = parameters.filter((name) => !isPdiTemplateParameter(name))
  if (templateCount === TEMPLATE_PARAMETERS.length && extras.length === 0) {
    return (
      <span className="text-xs font-semibold bg-brand-50 text-brand-800 px-2 py-0.5 rounded">
        Pre-dispatch template
      </span>
    )
  }
  return (
    <div className="flex flex-wrap gap-1 max-w-md">
      {templateCount > 0 && (
        <span className="text-xs font-semibold bg-brand-50 text-brand-800 px-2 py-0.5 rounded">
          Pre-dispatch template ({templateCount})
        </span>
      )}
      {extras.map((param) => (
        <span
          key={param}
          className="text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-0.5 rounded"
        >
          {param}
        </span>
      ))}
    </div>
  )
}

export function ProductsTable({ products, onEdit, onDeactivate }) {
  if (!products.length) {
    return (
      <p className="text-center text-gray-500 font-semibold py-8">
        No products in the master yet. Create your first part below.
      </p>
    )
  }

  return (
    <ScrollTable label="Product master list" className="border-0">
      <table className="min-w-[720px] w-full text-left border-collapse text-sm">
        <thead>
          <tr className="bg-gray-50 text-xs text-gray-500 uppercase border-y border-gray-200">
            <th className="p-4 font-bold">Part #</th>
            <th className="p-4 font-bold">Name</th>
            <th className="p-4 font-bold">Group</th>
            <th className="p-4 font-bold">Parameters</th>
            <th className="p-4 font-bold">Actions</th>
          </tr>
        </thead>
        <tbody>
          {products.map((product) => (
            <tr key={product.part_number} className="border-b border-gray-100 hover:bg-gray-50">
              <td className="p-4 font-mono font-bold text-gray-900">{product.part_number}</td>
              <td className="p-4 font-semibold text-gray-800">{product.part_name}</td>
              <td className="p-4 text-gray-600">{product.group || "—"}</td>
              <td className="p-4">
                <ProductChecks parameters={product.parameters} />
              </td>
              <td className="p-4 whitespace-nowrap">
                <div className="flex flex-wrap gap-3">
                  <PartQrButton product={product} />
                  <button
                    type="button"
                    onClick={() => onEdit(product)}
                    className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg px-3 text-brand-600 text-xs font-bold hover:bg-brand-50 active:scale-[0.98]"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeactivate(product)}
                    className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg px-3 text-red-600 text-xs font-bold hover:bg-red-50 active:scale-[0.98]"
                  >
                    Deactivate
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollTable>
  )
}
