import { useEffect, useState } from "react"
import { Download, FileText, Printer } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "../ui/qa-button"
import "./report-print.css"

const PRINT_HOST_ID = "inspection-report-print-host"

function mountPrintHost() {
  const source = document.getElementById("inspection-report-print")
  if (!source) return

  document.getElementById(PRINT_HOST_ID)?.remove()

  const host = document.createElement("div")
  host.id = PRINT_HOST_ID
  host.setAttribute("aria-hidden", "true")

  const clone = source.cloneNode(true)
  clone.removeAttribute("id")
  clone.querySelectorAll("img").forEach((img) => {
    if (img.complete && img.naturalWidth === 0) img.remove()
  })
  host.appendChild(clone)
  document.body.appendChild(host)
}

function removePrintHost() {
  document.getElementById(PRINT_HOST_ID)?.remove()
}

function dispositionClass(disposition = "") {
  const value = String(disposition).toUpperCase()
  if (value.includes("FAIL") || value.includes("REJECT")) {
    return "report-print-disposition report-print-disposition--fail"
  }
  if (value.includes("HOLD") || value.includes("MARGINAL")) {
    return "report-print-disposition report-print-disposition--hold"
  }
  return "report-print-disposition report-print-disposition--pass"
}

function formatDate(value) {
  if (!value) return new Date().toLocaleString()
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export function InspectionReportDialog({ open, report, inspector, onClose, onNewInspection }) {
  const logoKey = report?.report_id ?? ""
  const [hiddenLogoKey, setHiddenLogoKey] = useState(null)
  const showLogo = hiddenLogoKey !== logoKey

  useEffect(() => {
    if (!open || !report) {
      removePrintHost()
      return undefined
    }

    const onBeforePrint = () => mountPrintHost()
    const onAfterPrint = () => removePrintHost()
    window.addEventListener("beforeprint", onBeforePrint)
    window.addEventListener("afterprint", onAfterPrint)
    return () => {
      window.removeEventListener("beforeprint", onBeforePrint)
      window.removeEventListener("afterprint", onAfterPrint)
      removePrintHost()
    }
  }, [open, report])

  if (!report) return null

  const handlePrint = () => {
    mountPrintHost()
    window.print()
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader className="no-print">
          <DialogTitle className="flex items-center gap-2">
            <FileText className="size-5 text-brand-600" />
            Inspection report ready
          </DialogTitle>
          <DialogDescription>
            Review the AI-generated QA report. Print or save as PDF for records.
          </DialogDescription>
        </DialogHeader>

        <div className="report-print-actions no-print flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <Button variant="primary" onClick={handlePrint}>
            <Printer className="size-4" />
            Print / Save PDF
          </Button>
          <Button variant="muted" onClick={onNewInspection}>
            New inspection
          </Button>
        </div>

        <article className="report-print-root" id="inspection-report-print">
          <header className="report-print-header">
            <div className="report-print-brand">
              {showLogo && (
                <img
                  src="/logo.jpg"
                  alt="Rushab Industries"
                  onError={() => setHiddenLogoKey(logoKey)}
                />
              )}
              <div>
                <p className="text-sm font-bold text-brand-800">
                  {report.company || "Rushab Industries"}
                </p>
                <p className="text-xs text-muted-foreground">Quality Assurance Division</p>
              </div>
            </div>
            <div className="report-print-meta">
              <p>
                <strong>Report ID:</strong> {report.report_id}
              </p>
              <p>
                <strong>Date:</strong> {formatDate(report.inspection_date)}
              </p>
              <p>
                <strong>Inspector:</strong> {inspector || "N/A"}
              </p>
            </div>
          </header>

          <h1 className="report-print-title">{report.title}</h1>

          <div className="mb-3">
            <span className={dispositionClass(report.disposition)}>
              {report.disposition}
            </span>
          </div>

          {report.executive_summary && (
            <section className="report-print-summary">
              <p className="text-xs font-bold uppercase tracking-wide text-brand-700">
                Executive summary
              </p>
              <p className="mt-1 text-sm">{report.executive_summary}</p>
            </section>
          )}

          {report.sections?.map((section) => (
            <section key={section.heading} className="report-print-section">
              <h3>{section.heading}</h3>
              <p>{section.body}</p>
            </section>
          ))}

          {report.recommendations?.length > 0 && (
            <section className="report-print-recommendations">
              <h3 className="text-sm font-bold text-brand-800">Recommendations</h3>
              <ul>
                {report.recommendations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          )}

          <footer className="report-print-footer">
            <p>{report.generated_by || "Rushab Industries QA System"}</p>
            <p className="no-print mt-2 flex items-center gap-1">
              <Download className="size-3" />
              Use Print → Save as PDF for archival copy.
            </p>
          </footer>
        </article>
      </DialogContent>
    </Dialog>
  )
}
