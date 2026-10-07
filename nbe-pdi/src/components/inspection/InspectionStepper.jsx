import { CheckCircle2, ClipboardList, Layers, Package } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

const STEPS = [
  { label: "Stage", icon: Layers },
  { label: "Part", icon: Package },
  { label: "Lot", icon: ClipboardList },
  { label: "Inspect", icon: CheckCircle2 },
]

export function getInspectionProgress({ partNumber, intakeSubmitted, isAllRated }) {
  if (!partNumber) return { activeStep: 1, value: 25 }
  if (!intakeSubmitted) return { activeStep: 2, value: 50 }
  if (!isAllRated) return { activeStep: 3, value: 75 }
  return { activeStep: 3, value: 100 }
}

export function InspectionStepper({ partNumber, intakeSubmitted, isAllRated }) {
  const { activeStep, value } = getInspectionProgress({
    partNumber,
    intakeSubmitted,
    isAllRated,
  })

  return (
    <div className="mb-6 space-y-3">
      <Progress value={value} className="h-2 bg-brand-100" />
      <div className="grid grid-cols-4 gap-1">
        {STEPS.map((step, index) => {
          const Icon = step.icon
          const isComplete = index < activeStep
          const isActive = index === activeStep

          return (
            <div
              key={step.label}
              className={cn(
                "flex flex-col items-center gap-1 rounded-lg px-1 py-2 text-center transition-colors",
                isActive && "bg-brand-50 text-brand-700",
                isComplete && !isActive && "text-pass",
                !isComplete && !isActive && "text-muted-foreground",
              )}
            >
              <Icon
                className={cn(
                  "size-4",
                  isComplete && "text-pass",
                  isActive && "text-brand-600",
                )}
              />
              <span className="text-[10px] font-bold uppercase tracking-wide">
                {step.label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
