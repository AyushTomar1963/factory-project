export const ADMIN_TABS = [
  { id: "dashboard", label: "Dashboard", title: "Factory metrics" },
  { id: "products", label: "Product Master", title: "Part specifications" },
  { id: "suppliers", label: "Suppliers", title: "Supplier directory" },
  { id: "users", label: "Users", title: "Station accounts" },
  { id: "reports", label: "Reports", title: "IQC & store reports" },
]

export function getAdminTab(id) {
  return ADMIN_TABS.find((tab) => tab.id === id) ?? ADMIN_TABS[0]
}
