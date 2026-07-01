import { AlertTriangle, CircleCheck, CircleX } from "lucide-react"
import { RATING_OPTIONS } from "../../constants/inspection"
import { cn } from "@/lib/utils"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Card } from "../ui/qa-card"

const RATING_ICONS = {
  GREEN: CircleCheck,
  YELLOW: AlertTriangle,
  RED: CircleX,
}

export function ParameterRatings({ specData, measuredValues, onRate }) {
  if (!specData) return null

  return (
    <Card className="mb-6 transition-all hover:shadow-lg">
      <h3 className="mb-1 text-xl font-black text-gray-800">{specData.part_name}</h3>
      {specData.group && (
        <p className="mb-4 text-sm font-bold text-brand-600">Group: {specData.group}</p>
      )}
      <div className="space-y-4">
        {specData.parameters?.map((param) => (
          <div
            key={param}
            className="rounded-2xl border border-brand-100 bg-gradient-to-br from-white to-brand-50/40 p-3 shadow-sm"
          >
            <p className="mb-3 text-sm font-bold text-gray-800">{param}</p>
            <ToggleGroup
              type="single"
              value={measuredValues[param] || ""}
              onValueChange={(value) => value && onRate(param, value)}
              className="grid w-full grid-cols-3 gap-2"
              spacing={0}
            >
              {RATING_OPTIONS.map((rating) => {
                const Icon = RATING_ICONS[rating.value]
                const selected = measuredValues[param] === rating.value

                return (
                  <ToggleGroupItem
                    key={rating.value}
                    value={rating.value}
                    aria-label={rating.label}
                    className={cn(
                      "h-auto min-h-11 flex-col gap-1 rounded-xl px-2 py-3 text-xs font-black transition-all",
                      selected ? rating.active : rating.inactive,
                    )}
                  >
                    <Icon className="size-4" />
                    {rating.label}
                  </ToggleGroupItem>
                )
              })}
            </ToggleGroup>
          </div>
        ))}
      </div>
    </Card>
  )
}
