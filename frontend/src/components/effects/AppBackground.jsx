import { useEffect, useState } from "react"
import Lightfall from "./Lightfall"

const BRAND_COLORS = ["#bfdbfe", "#60a5fa", "#2563eb", "#4338ca"]

export function AppBackground() {
  const [reducedMotion, setReducedMotion] = useState(false)
  const [dpr, setDpr] = useState(1)

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    setReducedMotion(mq.matches)
    const onMotionChange = () => setReducedMotion(mq.matches)
    mq.addEventListener("change", onMotionChange)

    setDpr(Math.min(window.devicePixelRatio || 1, 1.5))

    return () => mq.removeEventListener("change", onMotionChange)
  }, [])

  if (reducedMotion) {
    return (
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0 bg-gradient-to-br from-brand-800 via-brand-700 to-indigo-900"
      />
    )
  }

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0">
      <Lightfall
        colors={BRAND_COLORS}
        backgroundColor="#1e40af"
        speed={0.55}
        streakCount={7}
        streakWidth={0.9}
        streakLength={1.1}
        glow={0.85}
        density={0.65}
        twinkle={0.5}
        zoom={2.8}
        backgroundGlow={0.55}
        opacity={0.42}
        mouseInteraction={false}
        dpr={dpr}
      />
      <div className="absolute inset-0 bg-gradient-to-b from-white/25 via-white/10 to-white/30" />
    </div>
  )
}
