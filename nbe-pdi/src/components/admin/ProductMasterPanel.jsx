import { useEffect, useState } from "react"
import {
  createProduct,
  deactivateProduct,
  fetchProducts,
  updateProduct,
} from "../../api/admin"
import { AlertBanner } from "../ui/StatusBadge"
import { SectionCard } from "./AdminAppShell"
import { visibleProducts } from "../../pdi-format"
import { usePdiFormat } from "../../hooks/usePdiFormat"
import { ProductForm, ProductsTable } from "./ProductMaster"

export function ProductMasterPanel({ token }) {
  const format = usePdiFormat(token)
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [editing, setEditing] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false

    fetchProducts(token)
      .then((data) => {
        if (!cancelled) setProducts(visibleProducts(data))
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
  }, [token, reloadKey])

  const refresh = () => setReloadKey((key) => key + 1)

  const handleCreate = async (payload) => {
    setIsSaving(true)
    setMessage("")
    try {
      const result = await createProduct(token, payload)
      setMessage(result.message)
      setEditing(null)
      refresh()
    } finally {
      setIsSaving(false)
    }
  }

  const handleUpdate = async (payload) => {
    if (!editing) return
    setIsSaving(true)
    setMessage("")
    try {
      const result = await updateProduct(token, editing.part_number, {
        part_name: payload.part_name,
        group_name: payload.group_name,
        parameters: payload.parameters,
      })
      setMessage(result.message)
      setEditing(null)
      refresh()
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeactivate = async (product) => {
    if (!window.confirm(`Deactivate ${product.part_number}? Workers will no longer load this part.`)) {
      return
    }
    setMessage("")
    try {
      const result = await deactivateProduct(token, product.part_number)
      setMessage(result.message)
      if (editing?.part_number === product.part_number) setEditing(null)
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="space-y-6">
      {error && <AlertBanner tone="error">{error}</AlertBanner>}
      {message && <AlertBanner tone="info">{message}</AlertBanner>}

      <SectionCard
        title="Product master"
        description="Parts saved here fill the pre-dispatch sheet. Tick the checks this part needs and set each frequency from 1 to 100 percent."
      >
        {loading ? (
          <p className="text-gray-500 font-semibold">Loading products...</p>
        ) : (
          <ProductsTable
            products={products}
            sections={format.sections}
            onEdit={setEditing}
            onDeactivate={handleDeactivate}
          />
        )}
      </SectionCard>

      <SectionCard
        title={editing ? `Edit ${editing.part_number}` : "Add new product"}
        description={
          editing
            ? "Part details stay editable. Tick or clear pre-dispatch lines, and set each frequency from 1 to 100 percent."
            : "Enter the part number and name. Every check starts clear. Use Check all, or tick the lines this part needs."
        }
        action={
          editing && (
            <button
              type="button"
              onClick={() => setEditing(null)}
              className="text-sm font-bold text-brand-600 hover:underline"
            >
              + New product instead
            </button>
          )
        }
      >
        <ProductForm
          key={`${editing?.part_number || "new"}-${format.sections.length}`}
          sections={format.sections}
          initial={editing}
          isSaving={isSaving}
          onSubmit={editing ? handleUpdate : handleCreate}
          onCancel={editing ? () => setEditing(null) : undefined}
        />
      </SectionCard>
    </div>
  )
}
