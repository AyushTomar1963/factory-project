import { useEffect, useId, useRef, useState } from "react"
import {
  Html5Qrcode,
  Html5QrcodeScannerState,
  Html5QrcodeSupportedFormats,
} from "html5-qrcode"
import { partNumberFromScan } from "../../lib/part-scan"
import "../../qr-scan.css"

const SIDE_KEY = "nbe-qr-side"

let cameraQueue = Promise.resolve()

function enqueue(job) {
  const run = cameraQueue.then(job, job)
  cameraQueue = run.then(
    () => {},
    () => {},
  )
  return run
}

function cameraMessage(error) {
  const text = String(error?.message || error || "")
  if (/notallowed|permission|denied/i.test(text)) {
    return "Camera permission was blocked. Allow the camera, or upload a photo of the code."
  }
  if (/notfound|no camera|device not found|requested device not found/i.test(text)) {
    return "That camera side was not found. Try the other side, or upload a photo."
  }
  if (/notreadable|in use|could not start|abort|trackstart/i.test(text)) {
    return "The camera is busy. Close other apps using it, or upload a photo of the code."
  }
  return "The camera did not start. Try the other side, or upload a photo of the code."
}

function isPermissionError(error) {
  return /notallowed|permission|denied/i.test(String(error?.message || error || ""))
}

function rememberedSide() {
  try {
    return sessionStorage.getItem(SIDE_KEY) === "front" ? "front" : "back"
  } catch {
    return "back"
  }
}

function rememberSide(side) {
  try {
    sessionStorage.setItem(SIDE_KEY, side)
  } catch {
    /* private mode */
  }
}

async function safeStop(scanner) {
  try {
    const state = scanner.getState()
    if (
      state === Html5QrcodeScannerState.SCANNING ||
      state === Html5QrcodeScannerState.PAUSED
    ) {
      await scanner.stop()
    }
  } catch {
    /* already stopped or still switching state */
  }
}

function scannerConfig() {
  return {
    verbose: false,
    formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
    experimentalFeatures: { useBarCodeDetectorIfSupported: false },
  }
}

function waitForWidth(element) {
  return new Promise((resolve) => {
    const started = performance.now()
    const tick = () => {
      if (!element.isConnected || element.clientWidth >= 80 || performance.now() - started > 1200) {
        resolve()
        return
      }
      requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}

function matchesSide(label, side) {
  const text = label || ""
  if (side === "back") return /back|rear|environment/i.test(text)
  return /front|user|face|selfie/i.test(text)
}

function attemptsForSide(cameras, side) {
  const labeled = cameras
    .filter((camera) => camera.id && matchesSide(camera.label, side))
    .map((camera) => camera.id)
  const facing = side === "front" ? { facingMode: "user" } : { facingMode: "environment" }
  return [...labeled, facing]
}

async function startAttempts(scanner, attempts, onCode, isActive) {
  let lastError = null
  for (const camera of attempts) {
    if (!isActive()) return false
    try {
      await scanner.start(
        camera,
        { fps: 10, disableFlip: false },
        (decoded) => {
          if (isActive()) onCode(decoded)
        },
        () => {},
      )
      if (!isActive()) {
        await safeStop(scanner)
        return false
      }
      return true
    } catch (error) {
      lastError = error
      await safeStop(scanner)
      if (isPermissionError(error)) throw error
    }
  }
  throw lastError || new Error("camera")
}

async function startCameraSide(scanner, side, onCode, isActive, allowFallback) {
  let cameras = []
  try {
    cameras = await Html5Qrcode.getCameras()
  } catch (error) {
    if (isPermissionError(error)) throw error
  }
  if (!isActive()) return { started: false, side }

  try {
    const started = await startAttempts(
      scanner,
      attemptsForSide(cameras, side),
      onCode,
      isActive,
    )
    if (started) return { started: true, side }
  } catch (error) {
    if (!allowFallback || isPermissionError(error) || !isActive()) throw error
  }

  if (!allowFallback || !isActive()) return { started: false, side }
  const other = side === "back" ? "front" : "back"
  const started = await startAttempts(
    scanner,
    attemptsForSide(cameras, other),
    onCode,
    isActive,
  )
  return { started, side: started ? other : side }
}

async function mirrorFile(file) {
  const bitmap = await createImageBitmap(file)
  const canvas = document.createElement("canvas")
  canvas.width = bitmap.width
  canvas.height = bitmap.height
  const context = canvas.getContext("2d")
  context.translate(canvas.width, 0)
  context.scale(-1, 1)
  context.drawImage(bitmap, 0, 0)
  bitmap.close?.()
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"))
  return new File([blob], "mirrored-code.png", { type: "image/png" })
}

export function QrScanPanel({ onDetected }) {
  const elementId = `qr-reader-${useId().replace(/:/g, "")}`
  const scannerRef = useRef(null)
  const onDetectedRef = useRef(onDetected)
  const handledRef = useRef(false)
  const noticeRef = useRef("")
  const requestedSide = useRef(rememberedSide())
  const fallbackRef = useRef(true)
  const [status, setStatus] = useState("Starting camera…")
  const [side, setSide] = useState(rememberedSide)
  const [session, setSession] = useState(0)

  useEffect(() => {
    onDetectedRef.current = onDetected
  }, [onDetected])

  const finish = (raw) => {
    if (handledRef.current) return true
    const part = partNumberFromScan(raw)
    if (!part) {
      noticeRef.current = "That code did not contain a part number. Try another code."
      setStatus(noticeRef.current)
      return false
    }
    handledRef.current = true
    onDetectedRef.current(part)
    return true
  }

  useEffect(() => {
    const element = document.getElementById(elementId)
    if (!element) return undefined
    let disposed = false
    const isActive = () => !disposed
    const scanner = new Html5Qrcode(elementId, scannerConfig())
    scannerRef.current = scanner
    const chosen = requestedSide.current === "front" ? "front" : "back"

    enqueue(async () => {
      if (disposed) return
      setStatus(chosen === "front" ? "Starting the front camera…" : "Starting the back camera…")
      await waitForWidth(element)
      if (disposed) return
      try {
        const result = await startCameraSide(
          scanner,
          chosen,
          finish,
          isActive,
          fallbackRef.current,
        )
        fallbackRef.current = false
        if (!result.started || disposed) return
        setSide(result.side)
        rememberSide(result.side)
        requestedSide.current = result.side
        const ready = result.side === "front"
          ? "Point the front camera at the label. A mirrored code is read too."
          : "Point the back camera at the label. A mirrored code is read too."
        setStatus(noticeRef.current || ready)
        noticeRef.current = ""
      } catch (error) {
        if (!disposed) {
          setStatus(noticeRef.current || cameraMessage(error))
          noticeRef.current = ""
        }
      }
    })

    return () => {
      disposed = true
      if (scannerRef.current === scanner) scannerRef.current = null
      enqueue(async () => {
        await safeStop(scanner)
        try {
          scanner.clear()
        } catch {
          /* already cleared */
        }
      })
    }
  }, [elementId, session])

  const onFile = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file || handledRef.current) return
    setStatus("Reading the photo…")
    const scanner = scannerRef.current
    if (!scanner) {
      setStatus("The scanner is not ready yet. Choose the photo again.")
      return
    }
    try {
      let accepted = false
      await enqueue(async () => {
        await safeStop(scanner)
        try {
          accepted = finish(await scanner.scanFile(file, false))
        } catch {
          accepted = finish(await scanner.scanFile(await mirrorFile(file), false))
        }
      })
      if (!accepted && !handledRef.current) setSession((current) => current + 1)
    } catch {
      if (!handledRef.current) {
        noticeRef.current = "No QR code was found in that photo. Try a closer, well-lit picture."
        setStatus(noticeRef.current)
        setSession((current) => current + 1)
      }
    }
  }

  const chooseSide = (next) => {
    fallbackRef.current = false
    requestedSide.current = next
    rememberSide(next)
    setSide(next)
    setSession((current) => current + 1)
  }

  return (
    <div className="space-y-3">
      <div id={elementId} className="qr-view" />
      <div className="grid grid-cols-2 gap-2" role="group" aria-label="Camera side">
        <button
          type="button"
          aria-pressed={side === "back"}
          onClick={() => chooseSide("back")}
          className={`min-h-11 rounded-lg px-3 text-sm font-bold ${
            side === "back"
              ? "bg-brand-700 text-white"
              : "border border-brand-200 bg-white text-brand-800"
          }`}
        >
          Back camera
        </button>
        <button
          type="button"
          aria-pressed={side === "front"}
          onClick={() => chooseSide("front")}
          className={`min-h-11 rounded-lg px-3 text-sm font-bold ${
            side === "front"
              ? "bg-brand-700 text-white"
              : "border border-brand-200 bg-white text-brand-800"
          }`}
        >
          Front camera
        </button>
      </div>
      <p className="text-sm font-semibold text-brand-900" data-qr-status>
        {status}
      </p>
      <label className="flex min-h-11 cursor-pointer items-center justify-center rounded-lg border border-brand-200 bg-brand-50 px-3 text-sm font-bold text-brand-800">
        Upload a photo of the code
        <input type="file" accept="image/*" className="sr-only" onChange={onFile} />
      </label>
    </div>
  )
}
