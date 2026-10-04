import { useState } from "react"
import { StoreAppShell } from "../components/store/StoreAppShell"
import { BinDashboard } from "../components/store/BinDashboard"
import { InwardPage } from "../components/store/InwardPage"
import { IssueMaterialForm } from "../components/store/IssueMaterialForm"
import { ReportsPanel } from "../components/store/ReportsPanel"
import { STORE_TABS } from "../constants/store"
import { useSection } from "../hooks/useSection"

export function StorePage({ token, username, onLogout }) {
  const [activeTab, setActiveTab] = useSection(
    "section",
    STORE_TABS.map((tab) => tab.id),
    "bins",
  )
  const [selectedBinId, setSelectedBinId] = useState(null)

  const handleStartInward = (binItemId) => {
    setSelectedBinId(binItemId)
    setActiveTab("inward")
  }

  return (
    <StoreAppShell
      activeTab={activeTab}
      onTabChange={setActiveTab}
      username={username}
      onLogout={onLogout}
    >
      {activeTab === "bins" && (
        <BinDashboard token={token} onStartInward={handleStartInward} />
      )}
      {activeTab === "inward" && (
        <InwardPage
          token={token}
          binItemId={selectedBinId}
          onIssueClick={() => setActiveTab("issue")}
        />
      )}
      {activeTab === "issue" && <IssueMaterialForm token={token} />}
      {activeTab === "reports" && <ReportsPanel token={token} defaultType="store" />}
    </StoreAppShell>
  )
}
