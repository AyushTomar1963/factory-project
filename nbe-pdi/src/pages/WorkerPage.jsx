import { useEffect } from "react"
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
import { StageSelector } from "../components/inspection/StageSelector"
import { Panel } from "../components/ui/qa-card"
import { Spinner } from "../components/ui/spinner"
import { useInspection } from "../hooks/useInspection"
import { useSection } from "../hooks/useSection"
import { PdiPage } from "./PdiPage"

export function WorkerPage({ token, onLogout }) {
  const [view, setView] = useSection("view", ["qc", "pdi"], "qc")
  const inspection = useInspection(token)

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
      <header className="sticky top-0 z-30 border-b border-white/15 bg-brand-800/95 text-white backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 pt-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-brand-100">
              Inspection
            </p>
            <h1 className="truncate text-lg font-black">
              {view === "pdi" ? "Pre-dispatch" : "QC station"}
            </h1>
          </div>
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
          className="mx-auto grid w-full max-w-6xl grid-cols-2 gap-1 px-4 pt-3 pb-3"
        >
          <button
            type="button"
            aria-current={view === "qc" ? "page" : undefined}
            onClick={() => setView("qc")}
            className={`min-h-11 rounded-lg px-3 text-sm font-bold ${
              view === "qc" ? "bg-white text-brand-800" : "text-white hover:bg-white/10"
            }`}
          >
            QC station
          </button>
          <button
            type="button"
            aria-current={view === "pdi" ? "page" : undefined}
            onClick={() => setView("pdi")}
            className={`min-h-11 rounded-lg px-3 text-sm font-bold ${
              view === "pdi" ? "bg-white text-brand-800" : "text-white hover:bg-white/10"
            }`}
          >
            Pre-dispatch
          </button>
        </nav>
      </header>

      {view === "pdi" ? (
        <PdiPage layout="framed" token={token} />
      ) : (
        <div className="flex justify-center px-4 pt-4 pb-8">
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
            isScanning={inspection.isScanning}
            onStartScan={() => inspection.setIsScanning(true)}
            onCancelScan={() => inspection.setIsScanning(false)}
            onReset={inspection.resetInspection}
            onScan={inspection.loadPart}
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
