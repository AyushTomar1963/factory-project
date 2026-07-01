import { useState } from "react"
import {
  AlertTriangle,
  Bot,
  CircleCheck,
  CircleX,
  MessageSquareWarning,
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Spinner } from "@/components/ui/spinner"
import { Button } from "../ui/qa-button"
import { Input, Textarea } from "../ui/FormField"

export function OverallDecision({ onPass, onHold, onFail, disabled }) {
  const [failOpen, setFailOpen] = useState(false)

  return (
    <div className="space-y-3">
      <p className="text-center text-sm font-bold text-gray-600">Overall decision</p>
      <div className="grid grid-cols-3 gap-2">
        <Button
          variant="pass"
          size="lg"
          disabled={disabled}
          onClick={onPass}
          className="flex flex-col gap-1 py-4"
        >
          <CircleCheck className="size-5" />
          PASS
        </Button>
        <Button
          variant="hold"
          size="lg"
          disabled={disabled}
          onClick={onHold}
          className="flex flex-col gap-1 py-4"
        >
          <AlertTriangle className="size-5" />
          HOLD
        </Button>
        <Button
          variant="fail"
          size="lg"
          disabled={disabled}
          onClick={() => setFailOpen(true)}
          className="flex flex-col gap-1 py-4"
        >
          <CircleX className="size-5" />
          FAIL
        </Button>
      </div>

      <Dialog open={failOpen} onOpenChange={setFailOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mark part as FAIL?</DialogTitle>
            <DialogDescription>
              You will need to log a defect remark before the record is submitted.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="muted" size="sm" onClick={() => setFailOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="fail"
              size="sm"
              onClick={() => {
                setFailOpen(false)
                onFail()
              }}
            >
              Continue to defect log
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export function YellowSupervisorPanel({
  chatMessage,
  aiReply,
  isAskingAi,
  isSubmitting,
  onChatChange,
  onAsk,
  onCancel,
  onSubmit,
}) {
  return (
    <div className="mt-4 rounded-2xl border-2 border-amber-300 bg-gradient-to-br from-amber-50 to-white p-4 shadow-sm">
      <div className="mb-2 flex items-center gap-2">
        <MessageSquareWarning className="size-5 text-amber-700" />
        <h2 className="text-lg font-black text-yellow-800">Marginal — AI supervisor</h2>
      </div>
      <p className="mb-4 text-xs font-bold text-yellow-700">
        Ask the AI for guidance or log your doubt before escalating.
      </p>
      {aiReply && (
        <div className="mb-4 whitespace-pre-wrap rounded-xl border border-amber-200 bg-white p-3 text-sm text-gray-800 shadow-inner">
          <div className="mb-1 flex items-center gap-1 font-bold text-brand-600">
            <Bot className="size-4" />
            AI response
          </div>
          {aiReply}
        </div>
      )}
      <div className="mb-4 flex gap-2">
        <Input
          type="text"
          placeholder="E.g. Vibration slightly high — what to check?"
          value={chatMessage}
          onChange={(e) => onChatChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onAsk()
          }}
          className="flex-1 border-amber-300 focus-visible:border-amber-500"
        />
        <Button
          variant="primary"
          size="sm"
          disabled={isAskingAi || !chatMessage.trim()}
          onClick={onAsk}
          className="min-w-16"
        >
          {isAskingAi ? <Spinner className="size-4" /> : "Ask"}
        </Button>
      </div>
      <div className="flex gap-3">
        <Button variant="muted" size="block" className="w-1/3" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          variant="warning"
          size="block"
          className="w-2/3"
          disabled={isSubmitting}
          onClick={onSubmit}
        >
          Submit YELLOW record
        </Button>
      </div>
    </div>
  )
}

export function DefectRemarkPanel({
  remark,
  isSubmitting,
  onRemarkChange,
  onCancel,
  onSubmit,
}) {
  return (
    <div className="mt-4 rounded-2xl border border-red-200 bg-gradient-to-br from-red-50 to-white p-4 shadow-sm">
      <div className="mb-2 flex items-center gap-2">
        <CircleX className="size-5 text-red-600" />
        <h2 className="text-lg font-bold text-red-600">Log defect remark</h2>
      </div>
      <Textarea
        placeholder="Describe the defect (Hindi or English)…"
        value={remark}
        onChange={(e) => onRemarkChange(e.target.value)}
        className="mb-4 h-24 border-red-200 focus-visible:border-red-500"
      />
      <div className="flex gap-3">
        <Button variant="mutedLight" size="block" className="w-1/3 rounded-xl" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          variant="danger"
          size="block"
          className="w-2/3 rounded-xl font-black"
          disabled={isSubmitting || !remark}
          onClick={onSubmit}
        >
          {isSubmitting ? "Submitting…" : "Submit defect record"}
        </Button>
      </div>
    </div>
  )
}
