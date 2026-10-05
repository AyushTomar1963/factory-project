import { useCallback, useEffect, useState } from "react"
import { fetchPdiFormat, savePdiFormat } from "../api/pdi-format"
import { PDI_SECTIONS } from "../pdi"

let cached = null

export function usePdiFormat(token) {
  const [sections, setSections] = useState(cached || PDI_SECTIONS)
  const [ready, setReady] = useState(Boolean(cached))
  const [error, setError] = useState("")

  useEffect(() => {
    if (!token) return undefined
    let cancelled = false
    fetchPdiFormat(token)
      .then((next) => {
        if (cancelled) return
        const value = next.length ? next : PDI_SECTIONS
        cached = value
        setSections(value)
        setReady(true)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message || "Could not load the pre-dispatch format")
        setReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  const save = useCallback(
    async (next) => {
      await savePdiFormat(token, next)
      cached = next
      setSections(next)
    },
    [token],
  )

  return { sections, ready, error, save }
}
