const PRODUCTION_API_URL = "https://factory-project-2.onrender.com"

export const API_BASE =
  import.meta.env.VITE_API_URL?.trim() ||
  (import.meta.env.DEV ? "" : PRODUCTION_API_URL)

export const STORAGE_KEYS = {
  token: "factoryToken",
  role: "factoryRole",
  user: "factoryUser",
}

export const INSPECTION_STAGES = [
  { value: "Stage 1", label: "Stage 1: Base Assembly" },
  { value: "Stage 2", label: "Stage 2: Performance Testing" },
  { value: "Stage 3", label: "Stage 3: Final Packaging" },
]

export const CHECKING_FREQUENCIES = [
  0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100,
]

export const RATING_OPTIONS = [
  {
    value: "GREEN",
    label: "GO",
    active: "bg-green-600 text-white shadow-lg shadow-green-200 scale-[1.02] border-green-600",
    inactive:
      "bg-white text-green-700 border border-green-200 hover:border-green-300 hover:bg-green-50",
  },
  {
    value: "YELLOW",
    label: "NO GO",
    active: "bg-amber-500 text-white shadow-lg shadow-amber-200 scale-[1.02] border-amber-500",
    inactive:
      "bg-white text-amber-700 border border-amber-200 hover:border-amber-300 hover:bg-amber-50",
  },
  {
    value: "RED",
    label: "DOUBTFUL",
    active: "bg-red-600 text-white shadow-lg shadow-red-200 scale-[1.02] border-red-600",
    inactive:
      "bg-white text-red-700 border border-red-200 hover:border-red-300 hover:bg-red-50",
  },
]

export const STATUS_BADGE_STYLES = {
  GREEN: "bg-green-100 text-green-700",
  YELLOW: "bg-yellow-100 text-yellow-800",
  RED: "bg-red-100 text-red-700",
}
