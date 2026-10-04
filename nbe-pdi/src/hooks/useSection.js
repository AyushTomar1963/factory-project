import { useSearchParams } from "react-router-dom"

export function useSection(key, ids, fallback) {
  const [params, setParams] = useSearchParams()
  const current = params.get(key)
  const active = ids.includes(current) ? current : fallback

  const setActive = (id) => {
    const next = new URLSearchParams(params)
    if (!id || id === fallback) next.delete(key)
    else next.set(key, id)
    setParams(next)
    window.scrollTo({ top: 0, left: 0 })
  }

  return [active, setActive]
}
