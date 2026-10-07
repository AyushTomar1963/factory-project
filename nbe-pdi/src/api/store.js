import { apiFetch } from "./client"

export function fetchStoreBins(token, binSlug) {
  return apiFetch(`/api/store/bins/${binSlug}`, { token })
}

export function fetchStoreSummary(token) {
  return apiFetch("/api/store/summary", { token })
}

export function syncIqcToStore(token) {
  return apiFetch("/api/store/sync-iqc", { token, method: "POST" })
}

export function fetchBinItem(token, binItemId) {
  return apiFetch(`/api/store/bin/${binItemId}`, { token })
}

export function submitInward(token, binItemId, body) {
  return apiFetch(`/api/store/inward/${binItemId}`, {
    token,
    method: "POST",
    body,
  })
}

export function fetchGrns(token, partNo) {
  const query = partNo ? `?part_no=${encodeURIComponent(partNo)}` : ""
  return apiFetch(`/api/store/grns${query}`, { token })
}

export function submitIssue(token, body) {
  return apiFetch("/api/store/issue", { token, method: "POST", body })
}

export function fetchBuffers(token) {
  return apiFetch("/api/store/buffers", { token })
}

export function saveBuffer(token, body) {
  return apiFetch("/api/store/buffers", { token, method: "POST", body })
}

export function deleteBuffer(token, bufferId) {
  return apiFetch(`/api/store/buffers/${bufferId}`, { token, method: "DELETE" })
}
