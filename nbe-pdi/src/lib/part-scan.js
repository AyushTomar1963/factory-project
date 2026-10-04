export function partNumberFromScan(raw) {
  const text = String(raw ?? "").trim()
  if (!text) return ""

  const fromJson = readJsonPart(text)
  if (fromJson) return cleanPart(fromJson)

  const fromUrl = readUrlPart(text)
  if (fromUrl) return cleanPart(fromUrl)

  const labeled = text.match(
    /(?:^|[\n\r])\s*part(?:\s*(?:no|number))?\s*[:#-]\s*(\S+)/i,
  )
  if (labeled) return cleanPart(labeled[1])

  const inline = text.match(/\bpart(?:\s*(?:no|number))?\s*[:#-]\s*(\S+)/i)
  if (inline) return cleanPart(inline[1])

  return cleanPart(text.split(/\r?\n/)[0])
}

function cleanPart(value) {
  const part = String(value).trim().toUpperCase()
  if (!part || part.length > 64) return ""
  return part
}

function readJsonPart(text) {
  if (!text.startsWith("{") && !text.startsWith("[")) return ""
  try {
    const data = JSON.parse(text)
    if (!data || typeof data !== "object" || Array.isArray(data)) return ""
    return data.part_number || data.partNumber || data.part || data.pn || ""
  } catch {
    return ""
  }
}

function readUrlPart(text) {
  if (!/^https?:\/\//i.test(text)) return ""
  try {
    const url = new URL(text)
    const query =
      url.searchParams.get("part") ||
      url.searchParams.get("partNo") ||
      url.searchParams.get("part_number") ||
      url.searchParams.get("pn")
    if (query) return query
    const segment = url.pathname.split("/").filter(Boolean).pop()
    return segment ? decodeURIComponent(segment) : ""
  } catch {
    return ""
  }
}
