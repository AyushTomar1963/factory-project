import { useState, useEffect, useRef } from 'react'
import { Html5QrcodeScanner } from 'html5-qrcode'

function App() {
  // --- NEW: Multi-tenant SaaS States ---
  const [sheetId, setSheetId] = useState(localStorage.getItem("factorySheetId") || "")
  const [tempInput, setTempInput] = useState("")

  // --- Existing States ---
  const [partNumber, setPartNumber] = useState("")
  const [specData, setSpecData] = useState(null)
  const [stage, setStage] = useState("Stage 1")
  const [measuredValues, setMeasuredValues] = useState({})
  const [overallStatus, setOverallStatus] = useState(null)
  const [remark, setRemark] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [serverMessage, setServerMessage] = useState("")
  const [isScanning, setIsScanning] = useState(false)
  const [manualInput, setManualInput] = useState("")

  const hasScannedRef = useRef(false)

  // Fetch Part Parameters from Backend
  useEffect(() => {
    if (partNumber && sheetId) {
      setServerMessage("Fetching part configuration...")
      // FIX: Appended ?sheet_id=${sheetId} to the URL
      fetch(`http://localhost:8000/api/get-spec/${partNumber}?sheet_id=${sheetId}`)
        .then(res => {
          if (!res.ok) throw new Error("Part not found or invalid Sheet ID.")
          return res.json()
        })
        .then(data => {
          setSpecData(data)
          const initialValues = {}
          if (data.parameters) {
            data.parameters.forEach(param => {
              initialValues[param] = ""
            })
          }
          setMeasuredValues(initialValues)
          setServerMessage("")
        })
        .catch(err => {
          setServerMessage(err.message)
          setSpecData(null)
          setMeasuredValues({})
        })
    }
  }, [partNumber, sheetId])

  // Camera integration
  useEffect(() => {
    if (isScanning) {
      hasScannedRef.current = false
      const scanner = new Html5QrcodeScanner("reader", { qrbox: { width: 250, height: 250 }, fps: 5 })
      scanner.render((decodedText) => {
        if (hasScannedRef.current) return
        hasScannedRef.current = true
        setPartNumber(decodedText.trim())
        setIsScanning(false)
      }, (_err) => {})
      return () => { scanner.clear().catch(e => console.error(e)) }
    }
  }, [isScanning])

  const handleRating = (paramName, value) => {
    setMeasuredValues(prev => ({ ...prev, [paramName]: value }))
  }

  const handleReset = () => {
    setPartNumber("")
    setSpecData(null)
    setMeasuredValues({})
    setOverallStatus(null)
    setRemark("")
    setServerMessage("")
    setManualInput("")
  }

  // All parameters must have a rating selected
  const isAllRated = specData?.parameters?.every(param => measuredValues[param] !== "")

  const handleLogSubmission = async (finalStatus) => {
    if (!partNumber || !specData) return
    if (!isAllRated) { alert("Please rate ALL parameters before submitting."); return }
    if (finalStatus === "RED" && !remark) { setOverallStatus("RED"); return }

    setIsSubmitting(true)
    setServerMessage("Submitting inspection log...")

    try {
      const response = await fetch("http://localhost:8000/api/log-inspection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sheet_id: sheetId, // FIX: Send the sheet_id to the backend
          part_number: partNumber,
          part_name: specData.part_name,
          current_stage: stage,
          measured_values: measuredValues,
          status: finalStatus,
          worker_remark: remark || null
        })
      })

      const data = await response.json()
      if (response.ok) {
        setServerMessage(data.message)
        setTimeout(() => { handleReset() }, 3000)
      } else {
        setServerMessage(data.detail || "Server rejected the request.")
      }
    } catch {
      setServerMessage("Cannot reach backend. Is the Python server running?")
    } finally {
      setIsSubmitting(false)
    }
  }

  // Color config for the 3 buttons per parameter
  const ratings = [
    { value: "GREEN",  label: "✅ GO",      active: "bg-green-500 text-white",  inactive: "bg-gray-100 text-gray-500 border border-gray-300" },
    { value: "YELLOW", label: "⚠️ TIGHT",   active: "bg-yellow-400 text-gray-900", inactive: "bg-gray-100 text-gray-500 border border-gray-300" },
    { value: "RED",    label: "❌ LOOSE",    active: "bg-red-500 text-white",    inactive: "bg-gray-100 text-gray-500 border border-gray-300" },
  ]

  // --- THE SETUP SCREEN ---
  // If the tablet does not have a Sheet ID saved, show this login screen
  if (!sheetId) {
    return (
      <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-6">
        <div className="w-full max-w-md bg-white rounded-xl shadow-lg p-8 border border-gray-200">
          <h1 className="text-2xl font-bold text-center text-gray-800 mb-2">Factory Setup</h1>
          <p className="text-sm text-gray-600 text-center mb-6">
            Please paste your Google Sheet ID to connect this station. Make sure you have shared the sheet with our bot!
          </p>
          <input
            type="text"
            placeholder="Paste ID here..."
            value={tempInput}
            onChange={(e) => setTempInput(e.target.value)}
            className="w-full p-3 border-2 border-gray-300 rounded-lg mb-4 text-center font-mono"
          /><button
            onClick={() => {
              if (tempInput.trim()) {
                let finalId = tempInput.trim();
                
                // SMART EXTRACTOR: If they paste the full URL, this automatically grabs just the ID
                const match = finalId.match(/\/d\/([a-zA-Z0-9-_]+)/);
                if (match) {
                  finalId = match[1];
                }

                localStorage.setItem("factorySheetId", finalId);
                setSheetId(finalId);
              }
            }}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg transition-colors"
          >
            Connect Station
          </button>
          
        </div>
      </div>
    )
  }

  // --- MAIN APP UI ---
  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center p-6 relative">
      
      {/* TINY LOGOUT BUTTON */}
      <button 
        onClick={() => {
          localStorage.removeItem("factorySheetId");
          setSheetId("");
          handleReset();
        }}
        className="absolute top-4 right-4 text-xs font-bold text-gray-400 hover:text-red-500 transition-colors"
      >
        Change Sheet
      </button>

      <div className="w-full max-w-md bg-white rounded-xl shadow-lg p-8 mt-10 border border-gray-200">
        <h1 className="text-3xl font-bold text-center text-gray-800 mb-6">IQC Inspection Portal</h1>

        {/* Stage Selector */}
        <div className="mb-6">
          <label className="block text-gray-700 font-bold mb-2 text-sm">Inspection Stage:</label>
          <select
            value={stage}
            onChange={(e) => setStage(e.target.value)}
            disabled={partNumber !== ""}
            className="w-full p-3 bg-gray-50 border-2 border-gray-300 rounded-lg text-gray-800 font-medium focus:border-blue-500 disabled:opacity-60"
          >
            <option value="Stage 1">Stage 1: Base Assembly</option>
            <option value="Stage 2">Stage 2: Performance Testing</option>
            <option value="Stage 3">Stage 3: Final Packaging</option>
          </select>
        </div>

        {/* Part Number Input / Display */}
        <div className="mb-6">
          {partNumber ? (
            <div className="bg-blue-50 border-2 border-blue-500 rounded-lg p-4 text-center relative">
              <span className="block text-sm text-blue-600 font-bold mb-1">Part Loaded</span>
              <span className="text-2xl font-black text-gray-900">{partNumber}</span>
              <button onClick={handleReset} className="absolute top-2 right-2 text-red-500 font-bold text-sm">Reset</button>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-gray-600 text-xs font-semibold mb-1">Dev Mode: Type Part Code</label>
                <input
                  type="text"
                  placeholder="e.g. BSH-01, RTR-02..."
                  value={manualInput}
                  onChange={(e) => setManualInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && manualInput.trim()) setPartNumber(manualInput.trim()) }}
                  className="w-full p-2 border border-dashed border-gray-400 rounded bg-yellow-50 text-center font-mono"
                />
              </div>
              {isScanning ? (
                <div>
                  <div id="reader" className="w-full rounded-lg overflow-hidden border-2 border-blue-500"></div>
                  <button onClick={() => setIsScanning(false)} className="w-full mt-4 bg-gray-500 text-white font-bold py-3 rounded-lg">Cancel Scan</button>
                </div>
              ) : (
                <button onClick={() => setIsScanning(true)} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-5 rounded-lg text-xl shadow-md transition-all active:scale-95">
                  📷 SCAN QR CODE
                </button>
              )}
            </div>
          )}
        </div>

        {/* Parameter Rating Cards */}
        {specData && (
          <div className="bg-gray-50 border border-gray-300 rounded-lg p-4 mb-6">
            <h3 className="text-xl font-black text-gray-800 mb-1">{specData.part_name}</h3>
            {specData.group && <p className="text-sm font-bold text-blue-600 mb-4">Group: {specData.group}</p>}

            <div className="space-y-4">
              {specData.parameters && specData.parameters.map((param, idx) => (
                <div key={idx} className="bg-white border border-gray-200 rounded-lg p-3">
                  <p className="text-gray-800 font-bold text-sm mb-2">{param}</p>
                  <div className="grid grid-cols-3 gap-2">
                    {ratings.map(r => (
                      <button
                        key={r.value}
                        onClick={() => handleRating(param, r.value)}
                        className={`py-2 px-1 rounded-lg text-xs font-bold transition-all ${
                          measuredValues[param] === r.value ? r.active : r.inactive
                        }`}
                      >
                        {r.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Overall Pass / Fail / Escalate — only shows when all params rated */}
        {specData && isAllRated && !overallStatus && (
          <div className="space-y-3">
            <p className="text-center text-gray-600 font-bold text-sm">Overall Decision:</p>
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => handleLogSubmission("GREEN")}
                disabled={isSubmitting}
                className="bg-green-500 hover:bg-green-600 text-white font-bold py-4 rounded-lg text-sm shadow-sm"
              >
                ✅ PASS
              </button>
              <button
                onClick={() => handleLogSubmission("YELLOW")}
                disabled={isSubmitting}
                className="bg-yellow-400 hover:bg-yellow-500 text-gray-900 font-bold py-4 rounded-lg text-sm shadow-sm"
              >
                ⚠️ BOSS
              </button>
              <button
                onClick={() => handleLogSubmission("RED")}
                disabled={isSubmitting}
                className="bg-red-500 hover:bg-red-600 text-white font-bold py-4 rounded-lg text-sm shadow-sm"
              >
                ❌ FAIL
              </button>
            </div>
          </div>
        )}

        {/* Remark Box for RED */}
        {overallStatus === "RED" && (
          <div className="mt-4">
            <h2 className="text-lg font-bold text-red-600 mb-2">Log Defect Remark</h2>
            <textarea
              placeholder="Describe the defect (Hindi or English)..."
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              className="w-full p-4 border-2 border-red-300 rounded-lg h-24 text-base focus:outline-none focus:border-red-500 mb-4"
            />
            <div className="flex gap-4">
              <button onClick={() => setOverallStatus(null)} className="w-1/3 bg-gray-300 text-gray-800 font-bold py-3 rounded-lg">Cancel</button>
              <button
                onClick={() => handleLogSubmission("RED")}
                disabled={isSubmitting || !remark}
                className="w-2/3 bg-red-600 text-white font-bold py-3 rounded-lg disabled:opacity-50"
              >
                Submit Defect Record
              </button>
            </div>
          </div>
        )}

        {/* Server Message */}
        {serverMessage && (
          <div className="mt-6 p-4 bg-blue-50 text-blue-800 font-bold text-center rounded-lg border border-blue-200">
            {serverMessage}
          </div>
        )}
      </div>
    </div>
  )
}

export default App