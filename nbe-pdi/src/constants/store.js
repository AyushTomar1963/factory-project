export const STORE_TABS = [
  { id: "bins", label: "Bin Dashboard", title: "Store bin dashboard" },
  { id: "inward", label: "Inward / GRN", title: "Material inward" },
  { id: "issue", label: "Issue Material", title: "Issue material" },
  { id: "reports", label: "Reports", title: "Store & IQC reports" },
]

export function getStoreTab(id) {
  return STORE_TABS.find((tab) => tab.id === id) || STORE_TABS[0]
}

export const BIN_TABS = [
  { id: "ok", label: "OK", slug: "ok", binType: "OK" },
  { id: "rejected", label: "Rejected", slug: "rejected", binType: "REJECTED" },
  { id: "doubtful", label: "Doubtful", slug: "doubtful", binType: "DOUBTFUL" },
]
