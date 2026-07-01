import { useState } from "react"
import { AdminAppShell } from "../components/admin/AdminAppShell"
import { DashboardPanel } from "../components/admin/DashboardPanel"
import { ProductMasterPanel } from "../components/admin/ProductMasterPanel"
import { SuppliersPanel } from "../components/admin/SuppliersPanel"
import { UsersPanel } from "../components/admin/UsersPanel"

export function AdminDashboardPage({ token, username, onLogout }) {
  const [activeTab, setActiveTab] = useState("dashboard")

  return (
    <AdminAppShell
      activeTab={activeTab}
      onTabChange={setActiveTab}
      username={username}
      onLogout={onLogout}
    >
      {activeTab === "dashboard" && <DashboardPanel token={token} />}
      {activeTab === "products" && <ProductMasterPanel token={token} />}
      {activeTab === "suppliers" && <SuppliersPanel token={token} />}
      {activeTab === "users" && <UsersPanel token={token} />}
    </AdminAppShell>
  )
}
