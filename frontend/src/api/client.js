import { API_BASE } from "../constants/inspection"

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

export async function apiFetch(path, { token, method = "GET", body, form } = {}) {
  const headers = {}
  let requestBody

  if (form) {
    requestBody = form
    headers["Content-Type"] = "application/x-www-form-urlencoded"
  } else if (body !== undefined) {
    requestBody = JSON.stringify(body)
    headers["Content-Type"] = "application/json"
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: requestBody,
  })

  let data = null
  const contentType = response.headers.get("content-type") || ""
  if (contentType.includes("application/json")) {
    data = await response.json()
  }

  if (!response.ok) {
    const message =
      (data && (data.detail || data.message)) || `Request failed (${response.status})`
    throw new ApiError(message, response.status)
  }

  return data
}
