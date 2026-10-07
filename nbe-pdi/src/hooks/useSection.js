import { useSearchParams } from "react-router-dom"

export function useSection(key, ids, fallback) {
  const [params, setParams] = useSearchParams()
  const current = params.get(key)
  const active = ids.includes(current) ? current : fallback

  const setActive = (id) => {
    const next = new URLSearchParams(params)
    next.delete("menu")
    next.delete("edit")
    if (!id || id === fallback) next.delete(key)
    else next.set(key, id)
    if (next.toString() === params.toString()) return
    setParams(next, { replace: params.get("menu") === "1" })
    window.scrollTo({ top: 0, left: 0 })
  }

  return [active, setActive]
}

export function returnToPrevious(fallback) {
  const index = window.history.state?.idx
  if (typeof index === "number" && index > 0) {
    window.history.back()
    return
  }
  fallback()
}
