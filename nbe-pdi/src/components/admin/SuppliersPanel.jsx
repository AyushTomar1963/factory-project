import { useEffect, useState } from "react"
import { createSupplier, fetchSuppliersAdmin } from "../../api/admin"
import { Button } from "../ui/qa-button"
import { FormField, Input, Textarea } from "../ui/FormField"
import { AlertBanner } from "../ui/StatusBadge"
import { SectionCard } from "./AdminAppShell"

export function SuppliersPanel({ token }) {
  const [suppliers, setSuppliers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [name, setName] = useState("")
  const [contact, setContact] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false

    fetchSuppliersAdmin(token)
      .then((data) => {
        if (!cancelled) setSuppliers(data)
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

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setIsSaving(true)
    setError("")
    setMessage("")
    try {
      const result = await createSupplier(token, {
        supplier_name: name.trim(),
        contact_info: contact.trim() || null,
      })
      setMessage(result.message)
      setName("")
      setContact("")
      setReloadKey((key) => key + 1)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      {error && <AlertBanner tone="error">{error}</AlertBanner>}
      {message && <AlertBanner tone="info">{message}</AlertBanner>}

      <SectionCard
        title="Registered suppliers"
        description="Suppliers appear in the worker lot intake dropdown."
      >
        {loading ? (
          <p className="text-gray-500 font-semibold">Loading suppliers...</p>
        ) : suppliers.length === 0 ? (
          <p className="text-center text-gray-500 font-semibold py-6">No suppliers yet.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {suppliers.map((s) => (
              <li key={s.id} className="py-3 flex flex-col sm:flex-row sm:justify-between gap-1">
                <span className="font-bold text-gray-900">{s.supplier_name}</span>
                <span className="text-sm text-gray-500">{s.contact_info || "No contact info"}</span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard title="Add supplier">
        <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
          <FormField label="Supplier name" htmlFor="supplier-name">
            <Input
              id="supplier-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Kirloskar Components Ltd"
              required
            />
          </FormField>
          <FormField label="Contact info (optional)" htmlFor="supplier-contact">
            <Textarea
              id="supplier-contact"
              value={contact}
              onChange={(e) => setContact(e.target.value)}
              placeholder="Phone, email, or address"
              className="h-20 border-gray-300 rounded-lg"
            />
          </FormField>
          <Button type="submit" variant="gradient" size="sm" disabled={isSaving}>
            {isSaving ? "Saving..." : "Add supplier"}
          </Button>
        </form>
      </SectionCard>
    </div>
  )
}
