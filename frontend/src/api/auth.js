import { apiFetch } from "./client"

export function login(username, password) {
  const form = new URLSearchParams()
  form.append("username", username)
  form.append("password", password)
  return apiFetch("/api/auth/login", { method: "POST", form })
}
