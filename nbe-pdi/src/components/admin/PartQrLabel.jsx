import { useEffect, useState } from "react"
import QRCode from "qrcode"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "../ui/qa-button"
import "../../qr-scan.css"

function printPartLabel({ dataUrl, partNumber, partName }) {
  document.getElementById("part-qr-print")?.remove()
  const host = document.createElement("div")
  host.id = "part-qr-print"
  const image = document.createElement("img")
  image.src = dataUrl
  image.alt = `QR code for ${partNumber}`
  const number = document.createElement("strong")
  number.textContent = partNumber
  const name = document.createElement("p")
  name.textContent = partName || ""
  host.append(image, number, name)
  document.body.appendChild(host)
  const previousTitle = document.title
  const safePart = String(partNumber).replace(/[^\w.-]+/g, "_")
  document.title = `NBE-QR-${safePart}`
  const restore = () => {
    host.remove()
    document.title = previousTitle
  }
  window.addEventListener("afterprint", restore, { once: true })
  window.print()
}

export function PartQrButton({ product }) {
  const [open, setOpen] = useState(false)
  const [dataUrl, setDataUrl] = useState("")

  useEffect(() => {
    if (!open) return undefined
    let cancelled = false
    QRCode.toDataURL(product.part_number, {
      margin: 2,
      width: 512,
      errorCorrectionLevel: "H",
    })
      .then((url) => {
        if (!cancelled) setDataUrl(url)
      })
      .catch(() => {
        if (!cancelled) setDataUrl("")
      })
    return () => {
      cancelled = true
    }
  }, [open, product.part_number])

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setDataUrl("")
          setOpen(true)
        }}
        className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg px-3 text-brand-600 text-xs font-bold hover:bg-brand-50 active:scale-[0.98]"
      >
        QR
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Part QR label</DialogTitle>
            <DialogDescription>
              Print this label and scan it from the QC station. The code is the part number.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col items-center gap-2 text-center">
            {dataUrl ? (
              <img
                src={dataUrl}
                alt={`QR code for ${product.part_number}`}
                className="h-56 w-56"
              />
            ) : (
              <p className="text-sm font-semibold text-gray-500">Preparing label…</p>
            )}
            <p className="font-mono text-lg font-black">{product.part_number}</p>
            <p className="text-sm font-semibold text-gray-600">{product.part_name}</p>
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="primary"
              size="sm"
              className="flex-1"
              disabled={!dataUrl}
              onClick={() =>
                printPartLabel({
                  dataUrl,
                  partNumber: product.part_number,
                  partName: product.part_name,
                })
              }
            >
              Print label
            </Button>
            {dataUrl && (
              <a
                href={dataUrl}
                download={`${String(product.part_number).replace(/[^\w.-]+/g, "_")}-qr.png`}
                className="inline-flex flex-1 items-center justify-center rounded-lg border border-brand-200 px-3 text-sm font-bold text-brand-800"
              >
                Download
              </a>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
