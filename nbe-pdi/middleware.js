const UPSTREAM = "https://factory-project-2.onrender.com"
const FORMAT_PART = "NBE-PDI-FORMAT"

export const config = {
  matcher: ["/api/products", "/api/pdi-format"],
}

async function readJson(response) {
  const text = await response.text()
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function json(body, status = 200) {
  return Response.json(body, { status })
}

async function callerIsSignedIn(authorization) {
  const session = await fetch(`${UPSTREAM}/api/suppliers`, {
    headers: { Authorization: authorization },
  })
  return session.ok
}

async function callerIsAdmin(authorization) {
  const users = await fetch(`${UPSTREAM}/api/admin/users`, {
    headers: { Authorization: authorization },
  })
  return users.ok
}

async function readerToken() {
  const username = process.env.NBE_PRODUCT_READER_USER
  const password = process.env.NBE_PRODUCT_READER_PASSWORD
  if (!username || !password) return null
  const login = await fetch(`${UPSTREAM}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
  })
  const body = await readJson(login)
  return login.ok ? body?.access_token || null : null
}

async function handleProducts(authorization) {
  const direct = await fetch(`${UPSTREAM}/api/products`, {
    headers: { Authorization: authorization },
  })
  if (direct.ok) {
    return new Response(await direct.text(), {
      status: 200,
      headers: { "content-type": "application/json" },
    })
  }
  if (direct.status !== 404) {
    const detail = await readJson(direct)
    return json(detail || { detail: "Could not read the product list" }, direct.status)
  }
  if (!(await callerIsSignedIn(authorization))) return json({ detail: "Not authenticated" }, 401)

  const token = await readerToken()
  if (!token) return json({ detail: "Product list is still unavailable" }, 503)

  const products = await fetch(`${UPSTREAM}/api/admin/products`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return new Response(await products.text(), {
    status: products.status,
    headers: { "content-type": "application/json" },
  })
}

async function readFormat(token) {
  const response = await fetch(`${UPSTREAM}/api/get-spec/${FORMAT_PART}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 404) return []
  const body = await readJson(response)
  if (!response.ok) return null
  return Array.isArray(body?.parameters) ? body.parameters : []
}

async function writeFormat(token, lines) {
  const payload = {
    part_name: "Pre-dispatch format",
    group_name: "Format",
    parameters: lines,
  }
  const update = await fetch(`${UPSTREAM}/api/admin/products/${FORMAT_PART}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })
  if (update.status !== 404) return update.ok
  const create = await fetch(`${UPSTREAM}/api/admin/products`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ part_number: FORMAT_PART, ...payload }),
  })
  return create.ok
}

async function handleFormat(request, authorization) {
  if (!(await callerIsSignedIn(authorization))) return json({ detail: "Not authenticated" }, 401)
  const token = await readerToken()
  if (!token) return json({ detail: "Pre-dispatch format is still unavailable" }, 503)

  if (request.method === "GET") {
    const lines = await readFormat(token)
    if (!lines) return json({ detail: "Could not read the pre-dispatch format" }, 502)
    return json({ lines })
  }

  if (request.method === "PUT") {
    if (!(await callerIsAdmin(authorization))) {
      return json({ detail: "Only an admin can edit the pre-dispatch format" }, 403)
    }
    const body = await readJson(request)
    const lines = Array.isArray(body?.lines) ? body.lines.filter((line) => typeof line === "string") : []
    if (!lines.length) return json({ detail: "Keep at least one checklist line." }, 400)
    const saved = await writeFormat(token, lines)
    if (!saved) return json({ detail: "Could not save the pre-dispatch format" }, 502)
    return json({ lines })
  }

  return json({ detail: "Method not allowed" }, 405)
}

export default async function middleware(request) {
  const authorization = request.headers.get("authorization") || ""
  if (!authorization.startsWith("Bearer ")) {
    return json({ detail: "Not authenticated" }, 401)
  }

  const path = new URL(request.url).pathname
  if (path === "/api/pdi-format") return handleFormat(request, authorization)
  return handleProducts(authorization)
}
