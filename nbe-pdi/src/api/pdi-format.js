import { apiFetch } from "./client"
import { FORMAT_PART, sectionsFromLines, sectionsToLines } from "../pdi-format"

const FORMAT_BODY = {
  part_name: "Pre-dispatch format",
  group_name: "Format",
}

export async function fetchPdiFormat(token) {
  try {
    const data = await apiFetch("/api/pdi-format", { token })
    return sectionsFromLines(data?.lines)
  } catch (error) {
    if (error.status !== 404) throw error
  }

  try {
    const spec = await apiFetch(`/api/get-spec/${FORMAT_PART}`, { token })
    return sectionsFromLines(spec?.parameters)
  } catch (error) {
    if (error.status === 404) return []
    throw error
  }
}

export async function savePdiFormat(token, sections) {
  const lines = sectionsToLines(sections)
  try {
    await apiFetch("/api/pdi-format", { token, method: "PUT", body: { lines } })
    return
  } catch (error) {
    if (error.status !== 404) throw error
  }

  const payload = { ...FORMAT_BODY, parameters: lines }
  try {
    await apiFetch(`/api/admin/products/${FORMAT_PART}`, {
      token,
      method: "PUT",
      body: payload,
    })
  } catch (error) {
    if (error.status !== 404) throw error
    await apiFetch("/api/admin/products", {
      token,
      method: "POST",
      body: { part_number: FORMAT_PART, ...payload },
    })
  }
}
