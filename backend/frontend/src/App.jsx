import { useState } from 'react'

function App() {
  const [partName, setPartName] = useState("")
  const [status, setStatus] = useState(null) // 'GREEN', 'YELLOW', 'RED'
  const [remark, setRemark] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [serverMessage, setServerMessage] = useState("")

  const handleAction = async (selectedStatus) => {
    if (!partName) {
      alert("Please enter or scan a part name first!")
      return
    }

    // If they click RED, just open the remark box. Don't submit yet.
    if (selectedStatus === "RED" && !remark) {
      setStatus("RED")
      return
    }

    setIsSubmitting(true)
    setServerMessage("Logging to Google Sheets...")

    try {
      const response = await fetch("https://factory-project-pcim.onrender.com/api/log-inspection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          part_name: partName,
          status: selectedStatus || status,
          worker_remark: remark || null,
        }),
      })

      const data = await response.json()
      setServerMessage(data.message)

      // Reset the form for the next scan
      setTimeout(() => {
        setPartName("")
        setStatus(null)
        setRemark("")
        setServerMessage("")
      }, 2000)

    } catch (error) {
      setServerMessage("Error: Could not connect to backend!")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center p-6">
      <div className="w-full max-w-md bg-white rounded-xl shadow-lg p-8 mt-10 border border-gray-200">

        <h1 className="text-3xl font-bold text-center text-gray-800 mb-8">
          Pump QA Scanner
        </h1>

        {/* Fake QR Scanner Input (For testing) */}
        <div className="mb-8">
          <label className="block text-gray-700 font-bold mb-2">Scanned Part:</label>
          <input
            type="text"
            placeholder="e.g., Slip Ring 45mm"
            value={partName}
            onChange={(e) => setPartName(e.target.value)}
            className="w-full p-4 border-2 border-gray-300 rounded-lg text-lg focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* The Traffic Light Buttons */}
        {!status && (
          <div className="flex flex-col gap-4">
            <button
              onClick={() => handleAction("GREEN")}
              disabled={isSubmitting}
              className="w-full bg-green-500 hover:bg-green-600 text-white font-bold py-6 rounded-lg text-2xl shadow-md transition-all active:scale-95"
            >
              ✅ PASS (GOOD)
            </button>

            <button
              onClick={() => handleAction("YELLOW")}
              disabled={isSubmitting}
              className="w-full bg-yellow-400 hover:bg-yellow-500 text-gray-900 font-bold py-6 rounded-lg text-2xl shadow-md transition-all active:scale-95"
            >
              ⚠️ HOLD (CHECK)
            </button>

            <button
              onClick={() => handleAction("RED")}
              disabled={isSubmitting}
              className="w-full bg-red-500 hover:bg-red-600 text-white font-bold py-6 rounded-lg text-2xl shadow-md transition-all active:scale-95"
            >
              ❌ REJECT (BAD)
            </button>
          </div>
        )}

        {/* The Red Workflow: Remark Box */}
        {status === "RED" && (
          <div className="animate-fade-in-up">
            <h2 className="text-xl font-bold text-red-600 mb-4">Log Defect Details</h2>
            <textarea
              placeholder="Why is it bad? (e.g., isme scratch hai...)"
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              className="w-full p-4 border-2 border-red-300 rounded-lg h-32 text-lg focus:outline-none focus:border-red-500 mb-4"
            />
            <div className="flex gap-4">
              <button
                onClick={() => setStatus(null)}
                className="w-1/3 bg-gray-300 hover:bg-gray-400 text-gray-800 font-bold py-4 rounded-lg text-lg transition-all active:scale-95"
              >
                Cancel
              </button>
              <button
                onClick={() => handleAction("RED")}
                disabled={isSubmitting || !remark}
                className="w-2/3 bg-red-500 hover:bg-red-600 text-white font-bold py-4 rounded-lg text-lg shadow-md transition-all active:scale-95 disabled:opacity-50"
              >
                {isSubmitting ? "Submitting..." : "❌ Confirm Reject"}
              </button>
            </div>
          </div>
        )}

        {/* Server feedback message */}
        {serverMessage && (
          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg text-center text-blue-700 font-semibold">
            {serverMessage}
          </div>
        )}

      </div>
    </div>
  )
}

export default App