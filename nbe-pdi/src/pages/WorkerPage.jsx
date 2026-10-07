import { useEffect, useRef } from "react"
import { useSearchParams } from "react-router-dom"
import { ChevronLeft } from "lucide-react"
import { toast } from "sonner"
import {
  DefectRemarkPanel,
  OverallDecision,
  YellowSupervisorPanel,
} from "../components/inspection/DecisionPanels"
import { InspectionReportDialog } from "../components/inspection/InspectionReportDialog"
import { InspectionStepper } from "../components/inspection/InspectionStepper"
import {
  LotIntakeForm,
  LotIntakeSummary,
} from "../components/inspection/LotIntakeForm"
import { ParameterRatings } from "../components/inspection/ParameterRatings"
import { PartLoader } from "../components/inspection/PartLoader"
import { QrScanPanel } from "../components/inspection/QrScanPanel"
import { StageSelector } from "../components/inspection/StageSelector"
import { Panel } from "../components/ui/qa-card"
import { Spinner } from "../components/ui/spinner"
import { useInspection } from "../hooks/useInspection"
import { returnToPrevious, useSection } from "../hooks/useSection"
import { PdiPage } from "./PdiPage"

export function WorkerPage({ token, onLogout }) {
  const [view] = useSection("view", ["qc", "pdi"], "qc")
  const [params, setParams] = useSearchParams()
  const closingScan = useRef(false)
  const scanning = params.get("scan") === "1" && view === "qc"
  const inspection = useInspection(token)

  const closeScan = () => {
    if (params.get("scan") !== "1" || closingScan.current) return
    const index = window.history.state?.idx
    if (typeof index === "number" && index > 0) {
      closingScan.current = true
      window.history.back()
      return
    }
    const next = new URLSearchParams(params)
    next.delete("scan")
    setParams(next, { replace: true })
  }

  const go = (id) => {
    if (params.get("scan") === "1" && (!id || id === "qc")) {
      closeScan()
      return
    }
    const next = new URLSearchParams(params)
    next.delete("scan")
    if (!id || id === "qc") next.delete("view")
    else next.set("view", id)
    if (next.toString() === params.toString()) return
    setParams(next, { replace: params.get("scan") === "1" })
    window.scrollTo({ top: 0, left: 0 })
  }

  const openScan = () => {
    if (params.get("scan") === "1") return
    const next = new URLSearchParams(params)
    next.delete("view")
    next.set("scan", "1")
    setParams(next)
  }

  useEffect(() => {
    if (params.get("scan") !== "1") closingScan.current = false
  }, [params])

  useEffect(() => {
    if (inspection.specError) toast.error(inspection.specError)
  }, [inspection.specError])

  useEffect(() => {
    if (inspection.submitMessage) {
      if (inspection.submitMessage.toLowerCase().includes("error")) {
        toast.error(inspection.submitMessage)
      } else {
        toast.success(inspection.submitMessage)
      }
    }
  }, [inspection.submitMessage])

  const handleIntakeError = (message) => {
    toast.warning(message)
  }

  const handleYellowSubmit = () => {
    const finalRemark = inspection.aiReply
      ? `Doubt: ${inspection.chatMessage} | AI Advice: ${inspection.aiReply}`
      : inspection.chatMessage || "Marginal - escalated"
    inspection.submitLog("YELLOW", finalRemark)
  }

  return (
    <div className="min-h-svh">
      <header className="phone-top sticky top-0 z-30 border-b border-white/15 bg-brand-800/95 text-white backdrop-blur">
        <div className="mx-auto flex w-full max-w-md items-center gap-2 px-3 pt-3">
          {view === "pdi" || scanning ? (
            <button
              type="button"
              onClick={() => (scanning ? closeScan() : returnToPrevious(() => go("qc")))}
              className="inline-flex min-h-11 shrink-0 items-center gap-0.5 rounded-lg pr-2 text-sm font-bold"
            >
              <ChevronLeft className="size-5" />
              Back
            </button>
          ) : (
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-brand-100">
              Inspection
            </p>
          )}
          <h1 className="min-w-0 flex-1 truncate text-lg font-black">
            {scanning ? "Scan QR" : view === "pdi" ? "Pre-dispatch" : "QC station"}
          </h1>
          <button
            type="button"
            onClick={onLogout}
            className="min-h-11 shrink-0 rounded-lg border border-white/30 bg-white/10 px-3 text-xs font-semibold"
          >
            Sign out
          </button>
        </div>
        <nav
          aria-label="Inspection sections"
          className="mx-auto grid w-full max-w-md grid-cols-2 gap-1 px-3 pt-3 pb-3"
        >
          <button
            type="button"
            aria-current={view === "qc" ? "page" : undefined}
            onClick={() => go("qc")}
            className={`min-h-11 rounded-lg px-3 text-center text-sm font-bold ${
              view === "qc" ? "bg-white text-brand-800" : "bg-white/10 text-white hover:bg-white/20"
            }`}
          >
            QC station
          </button>
          <button
            type="button"
            aria-current={view === "pdi" ? "page" : undefined}
            onClick={() => go("pdi")}
            className={`min-h-11 rounded-lg px-3 text-center text-sm font-bold ${
              view === "pdi" ? "bg-white text-brand-800" : "bg-white/10 text-white hover:bg-white/20"
            }`}
          >
            Pre-dispatch
          </button>
        </nav>
      </header>

      {view === "pdi" ? (
        <PdiPage layout="framed" token={token} />
      ) : scanning ? (
        <div className="phone-page mx-auto w-full max-w-md px-3 pt-4 pb-8">
          <QrScanPanel
            onDetected={(partNumber) => {
              closeScan()
              inspection.loadPart(partNumber)
            }}
          />
          <button
            type="button"
            onClick={closeScan}
            className="mt-3 min-h-11 w-full rounded-lg border border-brand-200 bg-white text-sm font-bold text-brand-800"
          >
            Back
          </button>
        </div>
      ) : (
        <div className="phone-page mx-auto flex w-full max-w-md justify-center px-3 pt-4 pb-8">
      <Panel className="rounded-2xl border">
        <InspectionStepper
          partNumber={inspection.partNumber}
          intakeSubmitted={inspection.intakeSubmitted}
          isAllRated={inspection.isAllRated}
        />

        <StageSelector
          stage={inspection.stage}
          onChange={inspection.setStage}
          disabled={Boolean(inspection.partNumber)}
        />

        <div className="mb-6">
          <PartLoader
            partNumber={inspection.partNumber}
            manualInput={inspection.manualInput}
            onManualChange={inspection.setManualInput}
            onManualSubmit={inspection.loadPartFromManual}
            onStartScan={openScan}
            onReset={inspection.resetInspection}
            isFetchingSpec={inspection.isFetchingSpec}
          />
        </div>

        {inspection.specData && !inspection.intakeSubmitted && (
          <LotIntakeForm
            intake={inspection.intake}
            suppliers={inspection.suppliers}
            onChange={inspection.updateIntake}
            onSubmit={inspection.submitIntake}
            onError={handleIntakeError}
          />
        )}

        {inspection.specData && inspection.intakeSubmitted && (
          <LotIntakeSummary
            intake={inspection.intake}
            onEdit={() => inspection.setIntakeSubmitted(false)}
          />
        )}

        {inspection.specData && inspection.intakeSubmitted && (
          <ParameterRatings
            specData={inspection.specData}
            measuredValues={inspection.measuredValues}
            onRate={inspection.setRating}
          />
        )}

        {inspection.specData &&
          inspection.intakeSubmitted &&
          inspection.isAllRated &&
          !inspection.overallStatus && (
            <OverallDecision
              disabled={inspection.isSubmitting}
              onPass={() => inspection.submitLog("GREEN")}
              onHold={() => inspection.setOverallStatus("YELLOW")}
              onFail={() => inspection.submitLog("RED")}
            />
          )}

        {inspection.overallStatus === "YELLOW" && (
          <YellowSupervisorPanel
            chatMessage={inspection.chatMessage}
            aiReply={inspection.aiReply}
            isAskingAi={inspection.isAskingAi}
            isSubmitting={inspection.isSubmitting}
            onChatChange={inspection.setChatMessage}
            onAsk={inspection.askAi}
            onCancel={() => {
              inspection.setOverallStatus(null)
              inspection.setRemark("")
            }}
            onSubmit={handleYellowSubmit}
          />
        )}

        {inspection.overallStatus === "RED" && (
          <DefectRemarkPanel
            remark={inspection.remark}
            isSubmitting={inspection.isSubmitting}
            onRemarkChange={inspection.setRemark}
            onCancel={() => {
              inspection.setOverallStatus(null)
              inspection.setRemark("")
            }}
            onSubmit={() => inspection.submitLog("RED")}
          />
        )}

        {inspection.isSubmitting && (
          <div className="mt-6 flex items-center justify-center gap-2 text-sm font-medium text-brand-600">
            <Spinner className="size-5" />
            Submitting inspection…
          </div>
        )}
      </Panel>
        </div>
      )}

      <InspectionReportDialog
        open={inspection.reportOpen}
        report={inspection.lastReport}
        inspector={inspection.reportInspector}
        onClose={() => inspection.setReportOpen(false)}
        onNewInspection={inspection.closeReportAndReset}
      />
    </div>
  )
}
