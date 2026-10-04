const UPSTREAM = "https://factory-project-2.onrender.com"

export const config = {
  matcher: "/api/products",
}

async function readJson(response) {
  const text = await response.text()
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export default async function middleware(request) {
  const authorization = request.headers.get("authorization") || ""
  if (!authorization.startsWith("Bearer ")) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 })
  }

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
    return Response.json(detail || { detail: "Could not read the product list" }, { status: direct.status })
  }

  const session = await fetch(`${UPSTREAM}/api/suppliers`, {
    headers: { Authorization: authorization },
  })
  if (!session.ok) {
    return Response.json({ detail: "Not authenticated" }, { status: session.status })
  }

  const username = process.env.NBE_PRODUCT_READER_USER
  const password = process.env.NBE_PRODUCT_READER_PASSWORD
  if (!username || !password) {
    return Response.json({ detail: "Product list is still unavailable" }, { status: 503 })
  }

  const login = await fetch(`${UPSTREAM}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
  })
  const loginBody = await readJson(login)
  if (!login.ok || !loginBody?.access_token) {
    return Response.json({ detail: "Could not read the product list" }, { status: 502 })
  }

  const products = await fetch(`${UPSTREAM}/api/admin/products`, {
    headers: { Authorization: `Bearer ${loginBody.access_token}` },
  })
  const body = await products.text()
  return new Response(body, {
    status: products.status,
    headers: { "content-type": "application/json" },
  })
}
