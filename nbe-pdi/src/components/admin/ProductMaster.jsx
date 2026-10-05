import { useState } from "react"
import { ScrollTable } from "@/components/ui/scroll-table"
import {
  PDI_SECTIONS,
  clampFrequency,
  isPdiTemplateParameter,
  parameterForStorage,
  templateFrequency,
  templateNames,
  templateSelection,
} from "../../pdi"
import { Button } from "../ui/qa-button"
import { FormField, Input } from "../ui/FormField"
import { PartQrButton } from "./PartQrLabel"

function TemplateChecks({ sections, selected, frequencies, onChange, onFrequency }) {
  const parameters = templateNames(sections)
  const selectedSet = new Set(selected)
  const toggle = (parameter) => {
    if (selectedSet.has(parameter)) onChange(selected.filter((name) => name !== parameter))
    else onChange([...selected, parameter])
  }

  const summary =
    selected.length === 0
      ? "No pre-dispatch lines selected. Tick the checks this part needs."
      : selected.length === parameters.length
        ? `All ${parameters.length} pre-dispatch checks selected.`
        : `${selected.length} of ${parameters.length} pre-dispatch checks selected.`

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="inline-flex min-h-11 items-center rounded-lg border border-brand-200 bg-white px-3 text-sm font-bold text-brand-800 active:scale-[0.98]"
          onClick={() => onChange(parameters)}
        >
          Check all
        </button>
        <button
          type="button"
          className="inline-flex min-h-11 items-center rounded-lg border border-gray-200 bg-white px-3 text-sm font-bold text-gray-700 active:scale-[0.98]"
          onClick={() => onChange([])}
        >
          Uncheck all
        </button>
      </div>
      <details className="rounded-lg border border-brand-100 bg-brand-50/40" open>
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-brand-900">
          {summary}
        </summary>
        <div className="max-h-[70vh] space-y-4 overflow-y-auto border-t border-brand-100 px-4 py-3">
          {sections.map((section) => (
            <div key={section.title}>
              <p className="text-xs font-bold uppercase tracking-wide text-brand-800">{section.title}</p>
              <ul className="mt-1">
                {section.items.map((item) => (
                  <li key={item.parameter} className="border-b border-brand-100/80 py-2 last:border-b-0">
                    <label className="flex items-start gap-2 text-sm text-gray-800">
                      <input
                        type="checkbox"
                        className="mt-0.5 size-5 shrink-0 accent-brand-700"
                        checked={selectedSet.has(item.parameter)}
                        onChange={() => toggle(item.parameter)}
                      />
                      <span className="min-w-0">
                        {item.parameter}
                        {item.specification ? (
                          <span className="block text-xs text-gray-500">{item.specification}</span>
                        ) : null}
                      </span>
                    </label>
                    <label className="mt-2 flex items-center gap-2 pl-7 text-xs font-semibold text-gray-600">
                      Frequency
                      <input
                        type="number"
                        min={1}
                        max={100}
                        step={1}
                        inputMode="numeric"
                        aria-label={`Frequency percent for ${item.parameter}`}
                        className="h-11 w-20 rounded-md border border-gray-300 bg-white px-2 text-center text-base font-semibold text-gray-900"
                        value={frequencies[item.parameter] ?? templateFrequency(item.parameter, sections)}
                        onChange={(event) => onFrequency(item.parameter, event.target.value)}
                        onBlur={() => {
                          if (frequencies[item.parameter] === "" || frequencies[item.parameter] == null) {
                            onFrequency(item.parameter, templateFrequency(item.parameter, sections))
                          }
                        }}
                      />
                      <span>% (1–100)</span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}

export function ParameterEditor({ parameters, onChange, allowEmpty = false, sections = PDI_SECTIONS }) {
  const [draft, setDraft] = useState("")

  const addParameter = () => {
    const trimmed = draft.trim()
    if (!trimmed || isPdiTemplateParameter(trimmed, sections)) {
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
          Extra part-specific checks, listed with the ticked pre-dispatch lines.
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

export function ProductForm({ initial, onSubmit, onCancel, isSaving, sections = PDI_SECTIONS }) {
  const isEdit = Boolean(initial?.part_number)
  const starting = initial?.parameters || []
  const parameters = templateNames(sections)
  const [partNumber, setPartNumber] = useState(initial?.part_number || "")
  const [partName, setPartName] = useState(initial?.part_name || "")
  const [groupName, setGroupName] = useState(initial?.group || "")
  const savedSelection = isEdit ? templateSelection(starting, sections) : { checks: [], frequencies: {} }
  const [templateChecks, setTemplateChecks] = useState(savedSelection.checks)
  const [frequencies, setFrequencies] = useState(() => ({
    ...Object.fromEntries(parameters.map((name) => [name, templateFrequency(name, sections)])),
    ...savedSelection.frequencies,
  }))
  const [extras, setExtras] = useState(starting.filter((name) => !isPdiTemplateParameter(name, sections)))
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
    const savedParameters = [
      ...parameters.filter((name) => templateChecks.includes(name)).map((name) =>
        parameterForStorage(name, frequencies[name], sections),
      ),
      ...extras.filter((name) => !isPdiTemplateParameter(name, sections)),
    ]
    if (savedParameters.length === 0) {
      setError("Select at least one pre-dispatch check, or add a parameter.")
      return
    }
    try {
      await onSubmit({
        part_number: partNumber.trim().toUpperCase(),
        part_name: partName.trim(),
        group_name: groupName.trim() || null,
        parameters: savedParameters,
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
      <TemplateChecks
        sections={sections}
        selected={templateChecks}
        frequencies={frequencies}
        onChange={setTemplateChecks}
        onFrequency={(parameter, value) => {
          if (value === "") {
            setFrequencies((current) => ({ ...current, [parameter]: "" }))
            return
          }
          setFrequencies((current) => ({ ...current, [parameter]: clampFrequency(value) }))
        }}
      />
      <ParameterEditor sections={sections} parameters={extras} onChange={setExtras} allowEmpty />
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

function ProductChecks({ parameters = [], sections = PDI_SECTIONS }) {
  const templateCount = parameters.filter((name) => isPdiTemplateParameter(name, sections)).length
  const extras = parameters.filter((name) => !isPdiTemplateParameter(name, sections))
  const total = templateNames(sections).length
  if (templateCount === total && extras.length === 0) {
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

export function ProductsTable({ products, onEdit, onDeactivate, sections = PDI_SECTIONS }) {
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
                <ProductChecks parameters={product.parameters} sections={sections} />
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
