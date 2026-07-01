import { apiFetch } from "./client"

export function fetchDashboardStats(token) {
  return apiFetch("/api/admin/dashboard-stats", { token })
}

export function fetchProducts(token) {
  return apiFetch("/api/admin/products", { token })
}

export function createProduct(token, payload) {
  return apiFetch("/api/admin/products", { method: "POST", token, body: payload })
}

export function updateProduct(token, partNumber, payload) {
  return apiFetch(`/api/admin/products/${encodeURIComponent(partNumber)}`, {
    method: "PUT",
    token,
    body: payload,
  })
}

export function deactivateProduct(token, partNumber) {
  return apiFetch(`/api/admin/products/${encodeURIComponent(partNumber)}`, {
    method: "DELETE",
    token,
  })
}

export function fetchSuppliersAdmin(token) {
  return apiFetch("/api/admin/suppliers", { token })
}

export function createSupplier(token, payload) {
  return apiFetch("/api/admin/suppliers", { method: "POST", token, body: payload })
}

export function fetchUsers(token) {
  return apiFetch("/api/admin/users", { token })
}

export function createUser(token, payload) {
  return apiFetch("/api/admin/users", { method: "POST", token, body: payload })
}
