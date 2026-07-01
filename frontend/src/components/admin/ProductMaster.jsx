import { useState } from "react"
import { Button } from "../ui/qa-button"
import { FormField, Input } from "../ui/FormField"

export function ParameterEditor({ parameters, onChange }) {
  const [draft, setDraft] = useState("")

  const addParameter = () => {
    const trimmed = draft.trim()
    if (!trimmed) return
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
          Add each dimension workers will rate (e.g. OD, ID, Length, Surface Finish).
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
      ) : (
        <p className="text-sm text-amber-700 font-semibold bg-amber-50 border border-amber-200 rounded-lg p-3">
          Add at least one parameter before saving.
        </p>
      )}
    </div>
  )
}

export function ProductForm({ initial, onSubmit, onCancel, isSaving }) {
  const isEdit = Boolean(initial?.part_number)
  const [partNumber, setPartNumber] = useState(initial?.part_number || "")
  const [partName, setPartName] = useState(initial?.part_name || "")
  const [groupName, setGroupName] = useState(initial?.group || "")
  const [parameters, setParameters] = useState(initial?.parameters || [])
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
    if (parameters.length === 0) {
      setError("Add at least one inspection parameter.")
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
      <ParameterEditor parameters={parameters} onChange={setParameters} />
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

export function ProductsTable({ products, onEdit, onDeactivate }) {
  if (!products.length) {
    return (
      <p className="text-center text-gray-500 font-semibold py-8">
        No products in the master yet. Create your first part below.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto -mx-6">
      <table className="w-full text-left border-collapse text-sm">
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
                <div className="flex flex-wrap gap-1 max-w-md">
                  {product.parameters?.map((param) => (
                    <span
                      key={param}
                      className="text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-0.5 rounded"
                    >
                      {param}
                    </span>
                  ))}
                </div>
              </td>
              <td className="p-4 whitespace-nowrap">
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => onEdit(product)}
                    className="text-brand-600 font-bold text-xs hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeactivate(product)}
                    className="text-red-600 font-bold text-xs hover:underline"
                  >
                    Deactivate
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
