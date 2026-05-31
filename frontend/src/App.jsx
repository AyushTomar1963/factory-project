import { useState, useEffect, useRef } from 'react'
import { Html5QrcodeScanner } from 'html5-qrcode'
const API_BASE = "https://factory-project-pcim.onrender.com"

const CHECKING_FREQUENCIES = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]

function App() {
  const [token, setToken] = useState(localStorage.getItem("factoryToken") || "")
  const [role, setRole] = useState(localStorage.getItem("factoryRole") || "")
  const [currentUser, setCurrentUser] = useState(localStorage.getItem("factoryUser") || "")
  const [sheetId, setSheetId] = useState(localStorage.getItem("factorySheetId") || "")
  const [loginUsername, setLoginUsername] = useState("")
  const [loginPassword, setLoginPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [tempSheetId, setTempSheetId] = useState(localStorage.getItem("factorySheetId") || "")
  const [authError, setAuthError] = useState("")
  const [isAuthenticating, setIsAuthenticating] = useState(false)

  // Intake form
  const [supplier, setSupplier] = useState("")
  const [suppliers, setSuppliers] = useState([])
  const [invoiceNumber, setInvoiceNumber] = useState("")
  const [lotQuantity, setLotQuantity] = useState("")
  const [checkingFrequency, setCheckingFrequency] = useState("")
  const [intakeSubmitted, setIntakeSubmitted] = useState(false)

  // Inspection
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

  // AI Chat
  const [chatMessage, setChatMessage] = useState("")
  const [aiReply, setAiReply] = useState("")
  const [isAskingAi, setIsAskingAi] = useState(false)

  const hasScannedRef = useRef(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    setAuthError("")
    setIsAuthenticating(true)
    let finalSheetId = tempSheetId.trim()
    const match = finalSheetId.match(/\/d\/([a-zA-Z0-9-_]+)/)
    if (match) finalSheetId = match[1]
    if (!finalSheetId || !loginUsername || !loginPassword) {
      setAuthError("All fields are required.")
      setIsAuthenticating(false)
      return
    }
    try {
      const formData = new URLSearchParams()
      formData.append("username", loginUsername)
      formData.append("password", loginPassword)
      const response = await fetch(`${API_BASE}/api/auth/login?sheet_id=${finalSheetId}`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData.toString(),
      })
      const data = await response.json()
      if (response.ok) {
        localStorage.setItem("factoryToken", data.access_token)
        localStorage.setItem("factoryRole", data.role)
        localStorage.setItem("factoryUser", data.username)
        localStorage.setItem("factorySheetId", finalSheetId)
        setToken(data.access_token)
        setRole(data.role)
        setCurrentUser(data.username)
        setSheetId(finalSheetId)
      } else {
        setAuthError(data.detail || "Authentication failed")
      }
    } catch (err) {
      setAuthError("Server unreachable. Check backend status.")
    } finally {
      setIsAuthenticating(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem("factoryToken")
    localStorage.removeItem("factoryRole")
    localStorage.removeItem("factoryUser")
    localStorage.removeItem("factorySheetId")
    setToken(""); setRole(""); setCurrentUser(""); setSheetId("")
    handleReset()
  }

  useEffect(() => {
    if (partNumber && sheetId && token) {
      setServerMessage("Fetching part configuration...")
      fetch(`${API_BASE}/api/get-spec/${partNumber}?sheet_id=${sheetId}`, {
        headers: { "Authorization": `Bearer ${token}` }
      })
        .then(res => { if (!res.ok) throw new Error("Part not found or access denied."); return res.json() })
        .then(data => {
          setSpecData(data)
          const initialValues = {}
          if (data.parameters) data.parameters.forEach(param => { initialValues[param] = "" })
          setMeasuredValues(initialValues)
          setServerMessage("")
        })
        .catch(err => { setServerMessage(err.message); setSpecData(null); setMeasuredValues({}) })
    }
  }, [partNumber, sheetId, token])

  useEffect(() => {
    if (token && sheetId) {
      fetch(`${API_BASE}/api/suppliers?sheet_id=${sheetId}`, {
        headers: { "Authorization": `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(data => setSuppliers(data.suppliers || []))
        .catch(() => setSuppliers([]))
    }
  }, [token, sheetId])

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

  const handleRating = (paramName, value) => setMeasuredValues(prev => ({ ...prev, [paramName]: value }))

  const handleReset = () => {
    setPartNumber(""); setSpecData(null); setMeasuredValues({})
    setOverallStatus(null); setRemark(""); setServerMessage(""); setManualInput("")
    setChatMessage(""); setAiReply("")
    setSupplier(""); setInvoiceNumber(""); setLotQuantity(""); setCheckingFrequency("")
    setIntakeSubmitted(false)
  }

  const isAllRated = specData?.parameters?.every(param => measuredValues[param] !== "")

  const handleIntakeSubmit = () => {
    if (!supplier || supplier === "Select Supplier...") { alert("Please select a supplier."); return }
    if (!invoiceNumber.trim()) { alert("Please enter invoice number."); return }
    if (!lotQuantity.trim()) { alert("Please enter lot quantity."); return }
    if (checkingFrequency === "") { alert("Please select checking frequency."); return }
    setIntakeSubmitted(true)
  }

  const handleAskAI = async () => {
    if (!chatMessage.trim()) return
    setIsAskingAi(true)
    setAiReply("Thinking...")
    try {
      const response = await fetch(`${API_BASE}/api/ai-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ part_name: specData.part_name, current_stage: stage, measured_values: measuredValues, worker_message: chatMessage })
      })
      const data = await response.json()
      if (response.ok) { setAiReply(data.reply) } else { setAiReply("AI Error: " + data.detail) }
    } catch { setAiReply("Network error connecting to AI.") }
    finally { setIsAskingAi(false) }
  }

  const handleLogSubmission = async (finalStatus, remarkOverride) => {
    if (!partNumber || !specData) return
    if (!isAllRated) { alert("Please rate ALL parameters before submitting."); return }
    if (finalStatus === "RED" && !remark) { setOverallStatus("RED"); return }
    setIsSubmitting(true)
    setServerMessage("Submitting inspection log...")
    try {
      const response = await fetch(`${API_BASE}/api/log-inspection`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({
          sheet_id: sheetId,
          part_number: partNumber,
          part_name: specData.part_name,
          current_stage: stage,
          measured_values: measuredValues,
          status: finalStatus,
          worker_remark: remarkOverride || remark || null,
          supplier: supplier,
          invoice_number: invoiceNumber,
          lot_quantity: lotQuantity,
          checking_frequency: checkingFrequency.toString(),
        })
      })
      const data = await response.json()
      if (response.ok) { setServerMessage(data.message); setTimeout(() => { handleReset() }, 3000) }
      else { setServerMessage(data.detail || "Server rejected the request.") }
    } catch { setServerMessage("Cannot reach backend. Is the Python server running?") }
    finally { setIsSubmitting(false) }
  }

  const ratings = [
    { value: "GREEN",  label: "✅ GO",    active: "bg-green-500 text-white",     inactive: "bg-gray-100 text-gray-500 border border-gray-300" },
    { value: "YELLOW", label: "⚠️ TIGHT", active: "bg-yellow-400 text-gray-900", inactive: "bg-gray-100 text-gray-500 border border-gray-300" },
    { value: "RED",    label: "❌ LOOSE", active: "bg-red-500 text-white",        inactive: "bg-gray-100 text-gray-500 border border-gray-300" },
  ]

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-6">
        <div className="w-full max-w-md bg-white rounded-xl shadow-lg p-8 border border-gray-200">
          <img src="/logo.png" alt="Kirloskar Logo" className="h-16 mx-auto mb-4" />
          <h1 className="text-2xl font-black text-center text-gray-900 mb-2">Kirloskar QA Portal</h1>
          <p className="text-sm text-gray-500 text-center mb-6">Authenticate to connect your station.</p>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">Google Sheet ID</label>
              <input type="text" required placeholder="Paste ID or full URL..." value={tempSheetId} onChange={(e) => setTempSheetId(e.target.value)} className="w-full p-3 border border-gray-300 rounded-lg text-sm font-mono" />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">Username</label>
              <input type="text" required placeholder="e.g. floor_worker" value={loginUsername} onChange={(e) => setLoginUsername(e.target.value)} className="w-full p-3 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  placeholder="••••••••"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  className="w-full p-3 border border-gray-300 rounded-lg text-sm pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(prev => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm"
                >
                  {showPassword ? "🙈" : "👁️"}
                </button>
              </div>
            </div>
            {authError && <p className="text-red-500 text-xs font-bold text-center">{authError}</p>}
            <button type="submit" disabled={isAuthenticating} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg transition-colors disabled:opacity-50">
              {isAuthenticating ? "Authenticating..." : "Login"}
            </button>
          </form>
        </div>
      </div>
    )
  }

  if (role === "admin") {
    return <AdminDashboard token={token} currentUser={currentUser} handleLogout={handleLogout} apiBase={API_BASE} />
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center p-6 relative">
      <div className="absolute top-4 right-4 flex flex-col items-end">
        <span className="text-xs font-bold text-blue-600 mb-1">Logged in as {currentUser}</span>
        <button onClick={handleLogout} className="text-xs font-bold text-gray-400 hover:text-red-500 transition-colors">Logout Station</button>
      </div>

      <div className="w-full max-w-md bg-white rounded-xl shadow-lg p-8 mt-10 border border-gray-200">
        <img src="/logo.png" alt="Kirloskar Logo" className="h-10 mx-auto mb-3" />
        <h1 className="text-3xl font-bold text-center text-gray-800 mb-6">IQC Inspection Portal</h1>

        {/* Stage Selector */}
        <div className="mb-6">
          <label className="block text-gray-700 font-bold mb-2 text-sm">Inspection Stage:</label>
          <select value={stage} onChange={(e) => setStage(e.target.value)} disabled={partNumber !== ""}
            className="w-full p-3 bg-gray-50 border-2 border-gray-300 rounded-lg text-gray-800 font-medium focus:border-blue-500 disabled:opacity-60">
            <option value="Stage 1">Stage 1: Base Assembly</option>
            <option value="Stage 2">Stage 2: Performance Testing</option>
            <option value="Stage 3">Stage 3: Final Packaging</option>
          </select>
        </div>

        {/* Part Number */}
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
                <input type="text" placeholder="e.g. BSH-01, RTR-02..." value={manualInput}
                  onChange={(e) => setManualInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && manualInput.trim()) setPartNumber(manualInput.trim()) }}
                  className="w-full p-2 border border-dashed border-gray-400 rounded bg-yellow-50 text-center font-mono" />
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

        {/* INTAKE FORM */}
        {specData && !intakeSubmitted && (
          <div className="bg-gray-50 border-2 border-blue-200 rounded-xl p-5 mb-6">
            <h2 className="text-lg font-black text-gray-800 mb-4">📋 Lot Intake Details</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Supplier</label>
                <select value={supplier} onChange={(e) => setSupplier(e.target.value)}
                  className="w-full p-3 border-2 border-gray-300 rounded-lg text-sm bg-white focus:border-blue-500 focus:outline-none">
                  <option value="">Select Supplier...</option>
                  {suppliers.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Invoice Number</label>
                <input type="text" placeholder="e.g. INV-2024-00123" value={invoiceNumber}
                  onChange={(e) => setInvoiceNumber(e.target.value)}
                  className="w-full p-3 border-2 border-gray-300 rounded-lg text-sm font-mono focus:border-blue-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Lot Quantity</label>
                <input type="number" placeholder="e.g. 500" value={lotQuantity}
                  onChange={(e) => setLotQuantity(e.target.value)}
                  className="w-full p-3 border-2 border-gray-300 rounded-lg text-sm focus:border-blue-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Checking Frequency (%)</label>
                <select value={checkingFrequency} onChange={(e) => setCheckingFrequency(e.target.value)}
                  className="w-full p-3 border-2 border-gray-300 rounded-lg text-sm bg-white focus:border-blue-500 focus:outline-none">
                  <option value="">Select frequency...</option>
                  {CHECKING_FREQUENCIES.map(f => <option key={f} value={f}>{f}%</option>)}
                </select>
              </div>
            </div>
            <button onClick={handleIntakeSubmit} className="w-full mt-5 bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg transition-colors">
              Confirm & Proceed to Inspection →
            </button>
          </div>
        )}

        {/* Intake Summary Badge */}
        {specData && intakeSubmitted && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-5 flex justify-between items-center">
            <div className="text-xs text-gray-700 space-y-0.5">
              <p><span className="font-bold">Supplier:</span> {supplier}</p>
              <p><span className="font-bold">Invoice:</span> {invoiceNumber} &nbsp;|&nbsp; <span className="font-bold">Lot:</span> {lotQuantity} pcs &nbsp;|&nbsp; <span className="font-bold">Freq:</span> {checkingFrequency}%</p>
            </div>
            <button onClick={() => setIntakeSubmitted(false)} className="text-xs text-blue-500 font-bold ml-2">Edit</button>
          </div>
        )}

        {/* Parameter Rating Cards */}
        {specData && intakeSubmitted && (
          <div className="bg-gray-50 border border-gray-300 rounded-lg p-4 mb-6">
            <h3 className="text-xl font-black text-gray-800 mb-1">{specData.part_name}</h3>
            {specData.group && <p className="text-sm font-bold text-blue-600 mb-4">Group: {specData.group}</p>}
            <div className="space-y-4">
              {specData.parameters && specData.parameters.map((param, idx) => (
                <div key={idx} className="bg-white border border-gray-200 rounded-lg p-3">
                  <p className="text-gray-800 font-bold text-sm mb-2">{param}</p>
                  <div className="grid grid-cols-3 gap-2">
                    {ratings.map(r => (
                      <button key={r.value} onClick={() => handleRating(param, r.value)}
                        className={`py-2 px-1 rounded-lg text-xs font-bold transition-all ${measuredValues[param] === r.value ? r.active : r.inactive}`}>
                        {r.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Overall Decision */}
        {specData && intakeSubmitted && isAllRated && !overallStatus && (
          <div className="space-y-3">
            <p className="text-center text-gray-600 font-bold text-sm">Overall Decision:</p>
            <div className="grid grid-cols-3 gap-2">
              <button onClick={() => handleLogSubmission("GREEN")} disabled={isSubmitting} className="bg-green-500 hover:bg-green-600 text-white font-bold py-4 rounded-lg text-sm shadow-sm">✅ PASS</button>
              <button onClick={() => setOverallStatus("YELLOW")} disabled={isSubmitting} className="bg-yellow-400 hover:bg-yellow-500 text-gray-900 font-bold py-4 rounded-lg text-sm shadow-sm">⚠️ BOSS</button>
              <button onClick={() => handleLogSubmission("RED")} disabled={isSubmitting} className="bg-red-500 hover:bg-red-600 text-white font-bold py-4 rounded-lg text-sm shadow-sm">❌ FAIL</button>
            </div>
          </div>
        )}

        {/* YELLOW: AI Supervisor */}
        {overallStatus === "YELLOW" && (
          <div className="mt-4 p-4 border-2 border-yellow-400 bg-yellow-50 rounded-xl">
            <h2 className="text-lg font-black text-yellow-800 mb-2">⚠️ Marginal: AI Supervisor</h2>
            <p className="text-xs text-yellow-700 mb-4 font-bold">Ask the AI for guidance or log your doubt before escalating.</p>
            {aiReply && (
              <div className="mb-4 p-3 bg-white border border-yellow-200 rounded-lg text-sm text-gray-800 shadow-inner whitespace-pre-wrap">
                <strong className="text-blue-600">AI Response:</strong><br />{aiReply}
              </div>
            )}
            <div className="flex gap-2 mb-4">
              <input type="text" placeholder="E.g. Vibration slightly high, what to check?" value={chatMessage}
                onChange={(e) => setChatMessage(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleAskAI() }}
                className="flex-1 p-3 border border-yellow-300 rounded-lg text-sm focus:outline-none focus:border-yellow-500" />
              <button onClick={handleAskAI} disabled={isAskingAi || !chatMessage.trim()}
                className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-4 rounded-lg disabled:opacity-50 text-sm">
                {isAskingAi ? "..." : "Ask"}
              </button>
            </div>
            <div className="flex gap-4">
              <button onClick={() => { setOverallStatus(null); setRemark("") }} className="w-1/3 bg-gray-300 text-gray-800 font-bold py-3 rounded-lg">Cancel</button>
              <button onClick={() => {
                const finalRemark = aiReply ? `Doubt: ${chatMessage} | AI Advice: ${aiReply}` : chatMessage || "Marginal - escalated"
                handleLogSubmission("YELLOW", finalRemark)
              }} disabled={isSubmitting} className="w-2/3 bg-yellow-500 hover:bg-yellow-600 text-gray-900 font-bold py-3 rounded-lg disabled:opacity-50">
                Submit YELLOW Record
              </button>
            </div>
          </div>
        )}

        {/* RED: Remark */}
        {overallStatus === "RED" && (
          <div className="mt-4">
            <h2 className="text-lg font-bold text-red-600 mb-2">Log Defect Remark</h2>
            <textarea placeholder="Describe the defect (Hindi or English)..." value={remark}
              onChange={(e) => setRemark(e.target.value)}
              className="w-full p-4 border-2 border-red-300 rounded-lg h-24 text-base focus:outline-none focus:border-red-500 mb-4" />
            <div className="flex gap-4">
              <button onClick={() => { setOverallStatus(null); setRemark("") }} className="w-1/3 bg-gray-300 text-gray-800 font-bold py-3 rounded-lg">Cancel</button>
              <button onClick={() => handleLogSubmission("RED")} disabled={isSubmitting || !remark} className="w-2/3 bg-red-600 text-white font-bold py-3 rounded-lg disabled:opacity-50">Submit Defect Record</button>
            </div>
          </div>
        )}

        {serverMessage && (
          <div className="mt-6 p-4 bg-blue-50 text-blue-800 font-bold text-center rounded-lg border border-blue-200">{serverMessage}</div>
        )}
      </div>
    </div>
  )
}

function AdminDashboard({ token, currentUser, handleLogout, apiBase }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    fetch(`${apiBase}/api/admin/dashboard-stats`, { headers: { "Authorization": `Bearer ${token}` } })
      .then(res => { if (!res.ok) throw new Error("Failed to fetch admin data"); return res.json() })
      .then(data => { setStats(data); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [token, apiBase])

  if (loading) return <div className="min-h-screen bg-gray-100 p-6 flex justify-center items-center font-bold text-gray-500">Loading factory metrics...</div>
  if (error) return <div className="min-h-screen bg-gray-100 p-6 flex justify-center items-center font-bold text-red-500">Error: {error}</div>

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <img src="/logo.png" alt="Kirloskar Logo" className="h-12" />
            <div>
              <h1 className="text-3xl font-black text-gray-900">Factory Control Center</h1>
              <p className="text-sm font-bold text-blue-600 mt-1">Logged in as {currentUser} (Admin)</p>
            </div>
          </div>
          <button onClick={handleLogout} className="bg-red-50 text-red-600 hover:bg-red-100 font-bold py-2 px-4 rounded-lg transition-colors">Logout Station</button>
        </div>

        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200 border-t-4 border-t-blue-500">
              <h3 className="text-gray-500 font-bold text-sm mb-1">Total All-Time</h3>
              <p className="text-3xl font-black text-gray-900">{stats.total_inspections}</p>
              <p className="text-xs text-gray-400 mt-2 font-bold">+ {stats.today_total} logged today</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200 border-t-4 border-t-green-500">
              <h3 className="text-gray-500 font-bold text-sm mb-1">Yield Rate</h3>
              <p className={`text-3xl font-black ${stats.yield_rate >= 90 ? 'text-green-600' : 'text-yellow-600'}`}>{stats.yield_rate}%</p>
              <p className="text-xs text-gray-400 mt-2 font-bold">{stats.failed_inspections} total defects</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200 border-t-4 border-t-red-500">
              <h3 className="text-gray-500 font-bold text-sm mb-1">Top Defect Reason</h3>
              <p className="text-xl font-black text-gray-900 mt-2 truncate" title={stats.top_defect}>{stats.top_defect}</p>
              <p className="text-xs text-gray-400 mt-2 font-bold">Generated by Gemini AI</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200 border-t-4 border-t-purple-500">
              <h3 className="text-gray-500 font-bold text-sm mb-2">Failure Heatmap</h3>
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-bold text-gray-600"><span>Stage 1</span><span className="text-red-500">{stats.stage_failures?.["Stage 1"] || 0}</span></div>
                <div className="flex justify-between text-xs font-bold text-gray-600"><span>Stage 2</span><span className="text-red-500">{stats.stage_failures?.["Stage 2"] || 0}</span></div>
                <div className="flex justify-between text-xs font-bold text-gray-600"><span>Stage 3</span><span className="text-red-500">{stats.stage_failures?.["Stage 3"] || 0}</span></div>
              </div>
            </div>
          </div>
        )}

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="p-6 border-b border-gray-200 bg-gray-50">
            <h2 className="text-xl font-bold text-gray-800">Recent Inspection Logs</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-white text-xs text-gray-500 uppercase border-b border-gray-200">
                  <th className="p-4 font-bold">Time</th>
                  <th className="p-4 font-bold">Part</th>
                  <th className="p-4 font-bold">Stage</th>
                  <th className="p-4 font-bold">Supplier</th>
                  <th className="p-4 font-bold">Invoice</th>
                  <th className="p-4 font-bold">Lot</th>
                  <th className="p-4 font-bold">Freq%</th>
                  <th className="p-4 font-bold">Worker</th>
                  <th className="p-4 font-bold">Status</th>
                  <th className="p-4 font-bold">AI Category</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {stats && stats.logs && [...stats.logs].reverse().map((log, idx) => (
                  <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                    <td className="p-4 text-gray-600 whitespace-nowrap">{log.Timestamp || "N/A"}</td>
                    <td className="p-4 font-bold text-gray-900">{log["Part Name"] || "N/A"}</td>
                    <td className="p-4 text-gray-600">{log.Stage || "N/A"}</td>
                    <td className="p-4 text-gray-600">{log.Supplier || "-"}</td>
                    <td className="p-4 text-gray-600 font-mono text-xs">{log.Invoice_Number || "-"}</td>
                    <td className="p-4 text-gray-600">{log.Lot_Quantity || "-"}</td>
                    <td className="p-4 text-gray-600">{log.Checking_Frequency ? `${log.Checking_Frequency}%` : "-"}</td>
                    <td className="p-4 text-gray-600">{log["Logged By"] || "Unknown"}</td>
                    <td className="p-4">
                      <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                        log.Status === "GREEN" ? "bg-green-100 text-green-700" :
                        log.Status === "YELLOW" ? "bg-yellow-100 text-yellow-800" : "bg-red-100 text-red-700"}`}>
                        {log.Status || "N/A"}
                      </span>
                    </td>
                    <td className="p-4 font-semibold text-gray-700">{log["AI Category"] || "-"}</td>
                  </tr>
                ))}
                {stats?.logs?.length === 0 && (
                  <tr><td colSpan="10" className="p-8 text-center text-gray-500 font-bold">No inspection logs found yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App