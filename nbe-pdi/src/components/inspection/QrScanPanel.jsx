import { useEffect, useId, useRef, useState } from "react"
import {
  Html5Qrcode,
  Html5QrcodeScannerState,
  Html5QrcodeSupportedFormats,
} from "html5-qrcode"
import { partNumberFromScan } from "../../lib/part-scan"
import "../../qr-scan.css"

const CAMERA_KEY = "nbe-qr-camera"

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
    return "No camera was found. Upload a photo of the code instead."
  }
  if (/notreadable|in use|could not start|abort|trackstart/i.test(text)) {
    return "The camera is busy. Close other apps using it, or upload a photo of the code."
  }
  return "The camera did not start. Upload a photo of the code instead."
}

function isPermissionError(error) {
  return /notallowed|permission|denied/i.test(String(error?.message || error || ""))
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

function rememberCamera(id) {
  if (!id) return
  try {
    sessionStorage.setItem(CAMERA_KEY, id)
  } catch {
    /* private mode */
  }
}

function rememberedCamera() {
  try {
    return sessionStorage.getItem(CAMERA_KEY) || ""
  } catch {
    return ""
  }
}

async function startBestCamera(scanner, preferredId, onCode, isActive) {
  let cameras = []
  try {
    cameras = await Html5Qrcode.getCameras()
  } catch (error) {
    if (isPermissionError(error) || !isActive()) throw error
  }
  if (!isActive()) return { started: false, cameras }

  const ordered = []
  const preferred = cameras.find((camera) => camera.id === preferredId)
  const back = cameras.find((camera) => /back|rear|environment/i.test(camera.label || ""))
  if (preferred) ordered.push(preferred.id)
  if (back && !ordered.includes(back.id)) ordered.push(back.id)
  for (const camera of cameras) {
    if (camera.id && !ordered.includes(camera.id)) ordered.push(camera.id)
  }
  const attempts = ordered.length
    ? ordered
    : [{ facingMode: "environment" }, { facingMode: "user" }]

  let lastError = null
  for (const camera of attempts) {
    if (!isActive()) return { started: false, cameras }
    try {
      await scanner.start(
        camera,
        { fps: 10 },
        (decoded) => {
          if (isActive()) onCode(decoded)
        },
        () => {},
      )
      if (!isActive()) {
        await safeStop(scanner)
        return { started: false, cameras }
      }
      return {
        started: true,
        cameras,
        id: typeof camera === "string" ? camera : "",
      }
    } catch (error) {
      lastError = error
      await safeStop(scanner)
      if (isPermissionError(error)) break
    }
  }
  throw lastError || new Error("camera")
}

export function QrScanPanel({ onDetected }) {
  const elementId = `qr-reader-${useId().replace(/:/g, "")}`
  const scannerRef = useRef(null)
  const onDetectedRef = useRef(onDetected)
  const handledRef = useRef(false)
  const [status, setStatus] = useState("Starting camera…")
  const [cameras, setCameras] = useState([])
  const [activeId, setActiveId] = useState("")
  const [session, setSession] = useState(0)
  const requestedId = useRef(rememberedCamera())
  const noticeRef = useRef("")

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

    enqueue(async () => {
      if (disposed) return
      setStatus("Starting camera…")
      await waitForWidth(element)
      if (disposed) return
      try {
        const result = await startBestCamera(
          scanner,
          requestedId.current,
          finish,
          isActive,
        )
        if (!result.started || disposed) return
        setCameras(result.cameras)
        setActiveId(result.id)
        rememberCamera(result.id)
        setStatus(
          noticeRef.current ||
            "Point the camera at the part label. The whole picture is scanned.",
        )
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
        const text = await scanner.scanFile(file, false)
        accepted = finish(text)
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

  const onCamera = (event) => {
    const id = event.target.value
    requestedId.current = id
    rememberCamera(id)
    setActiveId(id)
    setSession((current) => current + 1)
  }

  return (
    <div className="space-y-3">
      <div id={elementId} className="qr-view" />
      <p className="text-sm font-semibold text-brand-900" data-qr-status>
        {status}
      </p>
      {cameras.length > 1 && (
        <label className="block text-sm font-semibold text-brand-900">
          Camera
          <select
            value={activeId}
            onChange={onCamera}
            className="mt-1 min-h-11 w-full rounded-lg border border-brand-200 bg-white px-3 text-sm"
          >
            {cameras.map((camera, index) => (
              <option key={camera.id} value={camera.id}>
                {camera.label || `Camera ${index + 1}`}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="flex min-h-11 cursor-pointer items-center justify-center rounded-lg border border-brand-200 bg-brand-50 px-3 text-sm font-bold text-brand-800">
        Upload a photo of the code
        <input type="file" accept="image/*" className="sr-only" onChange={onFile} />
      </label>
    </div>
  )
}
