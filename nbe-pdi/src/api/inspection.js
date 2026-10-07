import { apiFetch } from "./client"
import { visibleProducts } from "../pdi-format"

export async function fetchPdiProducts(token) {
  try {
    return visibleProducts(await apiFetch("/api/products", { token }))
  } catch (error) {
    if (error.status !== 404) throw error
  }
  return visibleProducts(await apiFetch("/api/admin/products", { token }))
}

export function fetchPartSpec(token, partNumber) {
  return apiFetch(`/api/get-spec/${encodeURIComponent(partNumber)}`, { token })
}

export function fetchSuppliers(token) {
  return apiFetch("/api/suppliers", { token })
}

export function askAiSupervisor(token, payload) {
  return apiFetch("/api/ai-chat", { method: "POST", token, body: payload })
}

export function logInspection(token, payload) {
  return apiFetch("/api/log-inspection", { method: "POST", token, body: payload })
}
