import { useEffect } from "react"
import { toast } from "sonner"
import {
  DefectRemarkPanel,
  OverallDecision,
  YellowSupervisorPanel,
} from "../components/inspection/DecisionPanels"
import { InspectionStepper } from "../components/inspection/InspectionStepper"
import {
  LotIntakeForm,
  LotIntakeSummary,
} from "../components/inspection/LotIntakeForm"
import { ParameterRatings } from "../components/inspection/ParameterRatings"
import { PartLoader } from "../components/inspection/PartLoader"
import { StageSelector } from "../components/inspection/StageSelector"
import { PageHeader, WorkerShell } from "../components/layout/Shell"
import { Panel } from "../components/ui/qa-card"
import { Spinner } from "../components/ui/spinner"
import { useInspection } from "../hooks/useInspection"

export function WorkerPage({ token, onLogout }) {
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
    <WorkerShell
      header={
        <PageHeader
          eyebrow="Inspection"
          title="QC Station"
          onLogout={onLogout}
          compact
        />
      }
    >
      <Panel>
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
    </WorkerShell>
  )
}
