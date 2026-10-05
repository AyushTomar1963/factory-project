import { useEffect, useRef } from "react"
import { useSearchParams } from "react-router-dom"
import { useSidebar } from "@/components/ui/sidebar"

const MENU = "menu"

export function MobileMenuHistory() {
  const { isMobile, openMobile, setOpenMobile } = useSidebar()
  const [params, setParams] = useSearchParams()
  const open = params.get(MENU) === "1"
  const fromPop = useRef(false)
  const owned = useRef(false)
  const closing = useRef(false)
  const pushing = useRef(false)
  const menuWasOpen = useRef(false)

  useEffect(() => {
    menuWasOpen.current = open
  }, [open])

  useEffect(() => {
    const onPop = () => {
      if (!menuWasOpen.current) return
      fromPop.current = true
    }
    window.addEventListener("popstate", onPop)
    return () => window.removeEventListener("popstate", onPop)
  }, [])

  useEffect(() => {
    if (!isMobile) {
      if (openMobile) setOpenMobile(false)
      if (open) {
        const next = new URLSearchParams(params)
        next.delete(MENU)
        setParams(next, { replace: true })
      }
      return
    }

    if (!open) closing.current = false
    if (open) pushing.current = false

    const popped = fromPop.current
    fromPop.current = false
    if (popped) {
      owned.current = open
      if (!open && openMobile) setOpenMobile(false)
      return
    }

    if (closing.current) return

    if (openMobile && !open) {
      if (pushing.current) return
      pushing.current = true
      owned.current = true
      const next = new URLSearchParams(params)
      next.set(MENU, "1")
      setParams(next)
      return
    }

    if (!openMobile && open) {
      closing.current = true
      if (!owned.current || !(window.history.state?.idx > 0)) {
        const next = new URLSearchParams(params)
        next.delete(MENU)
        setParams(next, { replace: true })
        return
      }
      window.history.back()
    }
  }, [isMobile, open, openMobile, params, setOpenMobile, setParams])

  return null
}
