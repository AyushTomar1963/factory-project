import { API_BASE } from "../constants/inspection"

export async function fetchIqcReport(token, params = {}) {
  const query = new URLSearchParams(params).toString()
  const response = await fetch(`${API_BASE}/api/reports/iqc?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error("Failed to load IQC report")
  return response.json()
}

export async function fetchStoreReport(token, params = {}) {
  const query = new URLSearchParams(params).toString()
  const response = await fetch(`${API_BASE}/api/reports/store?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error("Failed to load store report")
  return response.json()
}

export async function exportReport(token, { type, format, ...filters }) {
  const query = new URLSearchParams({ type, format, ...filters }).toString()
  const response = await fetch(`${API_BASE}/api/reports/export?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error("Export failed")

  const blob = await response.blob()
  const disposition = response.headers.get("Content-Disposition") || ""
  const match = disposition.match(/filename="(.+)"/)
  const filename = match?.[1] || `${type}_report.${format}`

  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
