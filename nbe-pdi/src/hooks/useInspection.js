import { useCallback, useEffect, useRef, useState } from "react"
import { Html5QrcodeScanner } from "html5-qrcode"
import {
  askAiSupervisor,
  fetchPartSpec,
  fetchSuppliers,
  logInspection,
} from "../api/inspection"

const INITIAL_INTAKE = {
  supplier: "",
  invoiceNumber: "",
  lotQuantity: "",
  checkingFrequency: "",
}

export function useInspection(token) {
  const [stage, setStage] = useState("Stage 1")
  const [partNumber, setPartNumber] = useState("")
  const [manualInput, setManualInput] = useState("")
  const [specData, setSpecData] = useState(null)
  const [measuredValues, setMeasuredValues] = useState({})
  const [intake, setIntake] = useState(INITIAL_INTAKE)
  const [intakeSubmitted, setIntakeSubmitted] = useState(false)
  const [suppliers, setSuppliers] = useState([])
  const [overallStatus, setOverallStatus] = useState(null)
  const [remark, setRemark] = useState("")
  const [chatMessage, setChatMessage] = useState("")
  const [aiReply, setAiReply] = useState("")
  const [isAskingAi, setIsAskingAi] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isFetchingSpec, setIsFetchingSpec] = useState(false)
  const [specError, setSpecError] = useState("")
  const [submitMessage, setSubmitMessage] = useState("")
  const [lastReport, setLastReport] = useState(null)
  const [reportInspector, setReportInspector] = useState("")
  const [reportOpen, setReportOpen] = useState(false)
  const [isScanning, setIsScanning] = useState(false)
  const hasScannedRef = useRef(false)

  const resetInspection = useCallback(() => {
    setPartNumber("")
    setManualInput("")
    setSpecData(null)
    setMeasuredValues({})
    setOverallStatus(null)
    setRemark("")
    setSpecError("")
    setSubmitMessage("")
    setChatMessage("")
    setAiReply("")
    setLastReport(null)
    setReportInspector("")
    setReportOpen(false)
    setIntake(INITIAL_INTAKE)
    setIntakeSubmitted(false)
    setIsScanning(false)
  }, [])

  useEffect(() => {
    if (!token) return
    fetchSuppliers(token)
      .then((data) => setSuppliers(data.suppliers || []))
      .catch(() => setSuppliers([]))
  }, [token])

  const loadPart = useCallback(
    async (rawPartNumber) => {
      const trimmed = rawPartNumber.trim()
      if (!trimmed || !token) return

      setPartNumber(trimmed)
      setIsFetchingSpec(true)
      setSpecError("")
      setSpecData(null)
      setMeasuredValues({})
      setIntakeSubmitted(false)
      setOverallStatus(null)

      try {
        const data = await fetchPartSpec(token, trimmed)
        setSpecData(data)
        const initialValues = {}
        if (data.parameters) {
          data.parameters.forEach((param) => {
            initialValues[param] = ""
          })
        }
        setMeasuredValues(initialValues)
      } catch (err) {
        setSpecError(err.message)
        setSpecData(null)
        setMeasuredValues({})
      } finally {
        setIsFetchingSpec(false)
      }
    },
    [token],
  )

  useEffect(() => {
    if (!isScanning) return
    hasScannedRef.current = false
    const scanner = new Html5QrcodeScanner("reader", {
      qrbox: { width: 250, height: 250 },
      fps: 5,
    })
    scanner.render(
      (decodedText) => {
        if (hasScannedRef.current) return
        hasScannedRef.current = true
        loadPart(decodedText)
        setIsScanning(false)
      },
      () => {},
    )
    return () => {
      scanner.clear().catch(() => {})
    }
  }, [isScanning, loadPart])

  const isAllRated = specData?.parameters?.every(
    (param) => measuredValues[param] !== "",
  )

  const setRating = useCallback((paramName, value) => {
    setMeasuredValues((prev) => ({ ...prev, [paramName]: value }))
  }, [])

  const updateIntake = useCallback((field, value) => {
    setIntake((prev) => ({ ...prev, [field]: value }))
  }, [])

  const submitIntake = useCallback(() => {
    if (!intake.supplier) return "Please select a supplier."
    if (!intake.invoiceNumber.trim()) return "Please enter invoice number."
    if (!intake.lotQuantity.trim()) return "Please enter lot quantity."
    if (intake.checkingFrequency === "") return "Please select checking frequency."
    setIntakeSubmitted(true)
    return null
  }, [intake])

  const loadPartFromManual = useCallback(() => {
    if (manualInput.trim()) loadPart(manualInput)
  }, [loadPart, manualInput])

  const askAi = useCallback(async () => {
    if (!chatMessage.trim() || !specData) return
    setIsAskingAi(true)
    setAiReply("Thinking...")
    try {
      const data = await askAiSupervisor(token, {
        part_name: specData.part_name,
        current_stage: stage,
        measured_values: measuredValues,
        worker_message: chatMessage,
      })
      setAiReply(data.reply)
    } catch (err) {
      setAiReply(`AI Error: ${err.message}`)
    } finally {
      setIsAskingAi(false)
    }
  }, [chatMessage, measuredValues, specData, stage, token])

  const submitLog = useCallback(
    async (finalStatus, remarkOverride) => {
      if (!partNumber || !specData) return
      if (!isAllRated) return "Please rate ALL parameters before submitting."
      if (finalStatus === "RED" && !remark && !remarkOverride) {
        setOverallStatus("RED")
        return null
      }

      setIsSubmitting(true)
      setSubmitMessage("Submitting inspection log...")
      try {
        const data = await logInspection(token, {
          part_number: partNumber,
          part_name: specData.part_name,
          current_stage: stage,
          measured_values: measuredValues,
          status: finalStatus,
          worker_remark: remarkOverride || remark || null,
          supplier: intake.supplier,
          invoice_number: intake.invoiceNumber,
          lot_quantity: intake.lotQuantity,
          checking_frequency: intake.checkingFrequency.toString(),
        })
        setSubmitMessage(data.message)
        if (data.report) {
          setLastReport(data.report)
          setReportInspector(data.logged_by || "")
          setReportOpen(true)
        } else {
          setTimeout(resetInspection, 3000)
        }
        return null
      } catch (err) {
        setSubmitMessage(err.message)
        return err.message
      } finally {
        setIsSubmitting(false)
      }
    },
    [
      intake,
      isAllRated,
      measuredValues,
      partNumber,
      remark,
      resetInspection,
      specData,
      stage,
      token,
    ],
  )

  return {
    stage,
    setStage,
    partNumber,
    manualInput,
    setManualInput,
    loadPartFromManual,
    loadPart,
    specData,
    measuredValues,
    setRating,
    intake,
    updateIntake,
    intakeSubmitted,
    setIntakeSubmitted,
    suppliers,
    overallStatus,
    setOverallStatus,
    remark,
    setRemark,
    chatMessage,
    setChatMessage,
    aiReply,
    isAskingAi,
    isSubmitting,
    isFetchingSpec,
    specError,
    submitMessage,
    isScanning,
    setIsScanning,
    isAllRated,
    resetInspection,
    submitIntake,
    askAi,
    submitLog,
    lastReport,
    reportInspector,
    reportOpen,
    setReportOpen,
    closeReportAndReset: () => {
      setReportOpen(false)
      resetInspection()
    },
  }
}
