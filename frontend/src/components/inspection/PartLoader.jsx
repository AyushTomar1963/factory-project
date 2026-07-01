import { useState } from "react"
import {
  Camera,
  CheckCircle2,
  RotateCcw,
  Search,
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { Spinner } from "@/components/ui/spinner"
import { Button } from "../ui/qa-button"

export function PartLoader({
  partNumber,
  manualInput,
  onManualChange,
  onManualSubmit,
  isScanning,
  onStartScan,
  onCancelScan,
  onReset,
  isFetchingSpec,
}) {
  const [resetOpen, setResetOpen] = useState(false)

  if (partNumber) {
    return (
      <>
        <div className="relative rounded-2xl border-2 border-brand-200 bg-gradient-to-br from-brand-50 to-indigo-50 p-5 text-center shadow-sm">
          <div className="mb-1 flex items-center justify-center gap-2 text-sm font-bold text-brand-600">
            <CheckCircle2 className="size-4" />
            Part loaded
          </div>
          <p className="font-mono text-2xl font-black tracking-wide text-gray-900">
            {partNumber}
          </p>
          <button
            type="button"
            onClick={() => setResetOpen(true)}
            className="absolute top-3 right-3 flex items-center gap-1 text-xs font-bold text-red-600 hover:text-red-700"
          >
            <RotateCcw className="size-3.5" />
            Reset
          </button>
        </div>

        <Dialog open={resetOpen} onOpenChange={setResetOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Reset inspection?</DialogTitle>
              <DialogDescription>
                This clears the loaded part, lot details, and all ratings for this session.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2 sm:gap-0">
              <Button variant="muted" size="sm" onClick={() => setResetOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => {
                  onReset()
                  setResetOpen(false)
                }}
              >
                Reset
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </>
    )
  }

  return (
    <div className="space-y-4">
      <InputGroup className="h-12 border-2 border-dashed border-brand-200 bg-white">
        <InputGroupAddon>
          <Search className="size-4 text-brand-500" />
        </InputGroupAddon>
        <InputGroupInput
          type="text"
          placeholder="e.g. PN-1001, BSH-01..."
          value={manualInput}
          onChange={(e) => onManualChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onManualSubmit()
          }}
          className="text-center font-mono text-base"
          disabled={isFetchingSpec}
        />
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            onClick={onManualSubmit}
            disabled={!manualInput.trim() || isFetchingSpec}
            className="text-brand-700"
          >
            Load
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>

      {isFetchingSpec && (
        <div className="flex items-center justify-center gap-2 text-sm font-medium text-brand-600">
          <Spinner className="size-5" />
          Loading part spec…
        </div>
      )}

      <Button
        variant="scan"
        size="block"
        className="flex w-full items-center justify-center gap-2"
        onClick={onStartScan}
        disabled={isFetchingSpec}
      >
        <Camera className="size-5" />
        Scan QR code
      </Button>

      <Dialog open={isScanning} onOpenChange={(open) => !open && onCancelScan()}>
        <DialogContent className="max-w-md p-4 sm:max-w-lg" showCloseButton>
          <DialogHeader>
            <DialogTitle>Scan part QR code</DialogTitle>
            <DialogDescription>
              Point the camera at the part label. Scanning stops automatically when a code is read.
            </DialogDescription>
          </DialogHeader>
          <div
            id="reader"
            className="w-full overflow-hidden rounded-xl border-2 border-brand-300"
          />
          <DialogFooter>
            <Button variant="muted" size="block" className="w-full" onClick={onCancelScan}>
              Cancel scan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
