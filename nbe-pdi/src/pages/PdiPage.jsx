import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { fetchPdiProducts } from "../api/inspection"
import {
  PDI_COMPANY,
  PDI_METADATA_ROWS,
  PDI_OBSERVATIONS,
  PDI_TITLE,
  extraProductParameters,
  pdiItemKey,
  pdiSectionsForProduct,
} from "../pdi"
import "../pdi-form.css"

const PRINT_HOST_ID = "pdi-print-host"

function initialMeta() {
  const meta = {}
  for (const row of PDI_METADATA_ROWS) {
    for (const field of row) meta[field.key] = field.defaultValue || ""
  }
  return meta
}

function syncControlValues(root) {
  root.querySelectorAll("input").forEach((input) => {
    input.setAttribute("value", input.value)
  })
  root.querySelectorAll("textarea").forEach((textarea) => {
    textarea.textContent = textarea.value
  })
  root.querySelectorAll("select").forEach((select) => {
    Array.from(select.options).forEach((option) => {
      if (option.value === select.value) option.setAttribute("selected", "")
      else option.removeAttribute("selected")
    })
  })
}

function pdfTitle(meta, now = new Date()) {
  const pad = (value) => String(value).padStart(2, "0")
  const stamp = [
    pad(now.getDate()),
    pad(now.getMonth() + 1),
    now.getFullYear(),
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
  ].join("-")
  const part = String(meta?.partNo || "")
    .trim()
    .replace(/[^\w.-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
  return part ? `NBE-PDI-${part}-${stamp}` : `NBE-PDI-${stamp}`
}

function printedFieldValue(field) {
  if (field.type === "date" && /^\d{4}-\d{2}-\d{2}$/.test(field.value)) {
    const [year, month, day] = field.value.split("-")
    return `${day}/${month}/${year}`
  }
  return field.value
}

let previousDocumentTitle = ""

function applyPdfTitle(meta) {
  if (!previousDocumentTitle) previousDocumentTitle = document.title
  document.title = pdfTitle(meta)
}

function restorePdfTitle() {
  if (!previousDocumentTitle) return
  document.title = previousDocumentTitle
  previousDocumentTitle = ""
}

function cellLabel(cell) {
  const field = cell.querySelector("input, textarea")
  return field ? field.value : cell.textContent
}

function flattenSectionCells(root) {
  root.querySelectorAll("td.pdi-section[rowspan]").forEach((cell) => {
    const span = Number(cell.getAttribute("rowspan")) || 1
    const label = cellLabel(cell)
    cell.removeAttribute("rowspan")
    let row = cell.parentElement?.nextElementSibling
    for (let index = 1; index < span && row; index += 1) {
      const copy = cell.cloneNode(true)
      copy.textContent = label
      row.insertBefore(copy, row.firstChild)
      row = row.nextElementSibling
    }
  })
}

function mountPdiPrintHost() {
  const source = document.getElementById("pdi-report")
  if (!source) return

  syncControlValues(source)
  document.getElementById(PRINT_HOST_ID)?.remove()

  const host = document.createElement("div")
  host.id = PRINT_HOST_ID
  host.setAttribute("aria-hidden", "true")
  const clone = source.cloneNode(true)
  flattenSectionCells(clone)

  clone.querySelectorAll("input, textarea").forEach((field) => {
    const span = document.createElement("span")
    span.className = "pdi-filled-value"
    span.textContent = printedFieldValue(field)
    field.replaceWith(span)
  })

  clone.querySelectorAll("select").forEach((select) => {
    const chosen = select.options[select.selectedIndex]
    const value = document.createElement("span")
    const isObservation = select.classList.contains("pdi-observation")
    value.className = isObservation ? "pdi-observation-value" : "pdi-filled-value"
    if (isObservation && chosen?.value === "OK") value.classList.add("is-ok")
    if (isObservation && chosen?.value === "NOT OK") value.classList.add("is-not-ok")
    value.textContent = chosen?.value ? (isObservation ? chosen.textContent : chosen.value) : ""
    select.replaceWith(value)
  })

  host.appendChild(clone)
  document.body.appendChild(host)
}

function removePdiPrintHost() {
  document.getElementById(PRINT_HOST_ID)?.remove()
}

function masterKey(index) {
  return `master-${index}`
}

function LineField({ label, value, onChange, multiline = false }) {
  if (multiline) {
    return (
      <textarea
        className="pdi-cell-input pdi-line-remark"
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    )
  }
  return (
    <input
      className="pdi-cell-input"
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

export function PdiPage({ embedded = false, token, onLeave, onLogout }) {
  const [meta, setMeta] = useState(initialMeta)
  const [rows, setRows] = useState({})
  const [checkedBy, setCheckedBy] = useState("")
  const [approvedBy, setApprovedBy] = useState("")
  const [products, setProducts] = useState([])
  const [productStatus, setProductStatus] = useState(token ? "loading" : "missing")

  const selectedProduct = products.find((product) => product.part_number === meta.partNo)
  const reportSections = pdiSectionsForProduct(selectedProduct?.parameters)
  const extraParameters = extraProductParameters(selectedProduct?.parameters)
  const metaRef = useRef(meta)
  metaRef.current = meta

  useEffect(() => {
    if (!token) return undefined
    let cancelled = false
    fetchPdiProducts(token)
      .then((rows) => {
        if (cancelled) return
        setProducts(Array.isArray(rows) ? rows : [])
        setProductStatus("ready")
      })
      .catch((error) => {
        if (cancelled) return
        setProductStatus(
          error.status === 403
            ? "Product list is still admin-only on the live API."
            : error.message || "Could not load product master",
        )
      })
    return () => {
      cancelled = true
    }
  }, [token])

  const chooseProduct = (partNumber) => {
    const product = products.find((item) => item.part_number === partNumber)
    setMeta((current) => ({
      ...current,
      partNo: partNumber,
      partDescription: product ? product.part_name : current.partDescription,
    }))
    if (product) setRows({})
  }

  const rowValue = (key, defaults) => ({ ...defaults, ...rows[key] })

  const setRowField = (key, defaults, field, value) => {
    setRows((current) => ({
      ...current,
      [key]: { ...defaults, ...current[key], [field]: value },
    }))
  }

  useEffect(() => {
    const onBeforePrint = () => {
      applyPdfTitle(metaRef.current)
      mountPdiPrintHost()
    }
    const onAfterPrint = () => {
      restorePdfTitle()
      removePdiPrintHost()
    }
    window.addEventListener("beforeprint", onBeforePrint)
    window.addEventListener("afterprint", onAfterPrint)
    return () => {
      window.removeEventListener("beforeprint", onBeforePrint)
      window.removeEventListener("afterprint", onAfterPrint)
      removePdiPrintHost()
    }
  }, [])

  return (
    <div className="pdi-page">
      <div className="pdi-toolbar no-print">
        {!embedded && (
          <Link to="/" className="pdi-back-link">
            Back to portal
          </Link>
        )}
        {onLeave && (
          <button type="button" className="pdi-back-link" onClick={onLeave}>
            QC Station
          </button>
        )}
        {onLogout && (
          <button type="button" className="pdi-back-link pdi-toolbar-logout" onClick={onLogout}>
            Sign out
          </button>
        )}
        <p className="pdi-source">
          {productStatus === "loading" && "Loading product master…"}
          {productStatus === "ready" &&
            (products.length
              ? "Part details come from Product Master. Every cell can still be edited."
              : "Product Master has no parts yet. Add one there first.")}
          {productStatus !== "loading" && productStatus !== "ready" && productStatus !== "missing" && productStatus}
        </p>
        <button
          type="button"
          className="pdi-print-button"
          onClick={() => {
            applyPdfTitle(meta)
            mountPdiPrintHost()
            window.print()
          }}
        >
          Print / Save PDF
        </button>
      </div>

      <article id="pdi-report" className="pdi-sheet">
        <header className="pdi-brand">
          <img
            src="/nbe-logo.png"
            alt="New Bharat, NBE Motors Pvt. Ltd."
            className="pdi-logo"
          />
          <h1 className="pdi-company">{PDI_COMPANY}</h1>
          <p className="pdi-subtitle">{PDI_TITLE}</p>
        </header>

        <div className="pdi-meta">
          {PDI_METADATA_ROWS.flat().map((field) => (
            <label key={field.key} className="pdi-field">
              <span>{field.label}</span>
              {field.key === "partNo" ? (
                <>
                  <input
                    list="pdi-part-numbers"
                    aria-label="Part number from product master"
                    value={meta.partNo}
                    onChange={(event) => chooseProduct(event.target.value)}
                  />
                  <datalist id="pdi-part-numbers">
                    {products.map((product) => (
                      <option key={product.part_number} value={product.part_number}>
                        {product.part_name || product.part_number}
                      </option>
                    ))}
                  </datalist>
                </>
              ) : (
                <input
                  type={field.calendar ? "date" : "text"}
                  value={meta[field.key]}
                  onChange={(event) =>
                    setMeta((current) => ({ ...current, [field.key]: event.target.value }))
                  }
                />
              )}
            </label>
          ))}
        </div>

        <div className="pdi-table-wrap">
          <table className="pdi-table">
            <thead>
              <tr>
                <th>SR NO</th>
                <th>PARAMETER</th>
                <th>SPECIFICATION</th>
                <th>FREQ</th>
                <th>INSPECTION METHOD</th>
                <th>OBSERVATION</th>
                <th>REMARKS</th>
              </tr>
            </thead>
            <tbody>
              {extraParameters.length > 0 &&
                extraParameters.map((parameter, itemIndex) => {
                  const key = masterKey(itemIndex)
                  const defaults = {
                    section:
                      itemIndex === 0
                        ? selectedProduct?.group
                          ? `Product master · ${selectedProduct.group}`
                          : "Product master"
                        : "",
                    parameter,
                    specification: "",
                    freq: "100%",
                    method: "Product master",
                    observation: "",
                    remark: "",
                  }
                  const line = rowValue(key, defaults)
                  return (
                    <tr key={key}>
                      {itemIndex === 0 && (
                        <td className="pdi-section" rowSpan={extraParameters.length}>
                          <LineField
                            label="Section"
                            value={line.section}
                            onChange={(value) => setRowField(key, defaults, "section", value)}
                          />
                        </td>
                      )}
                      <td className="pdi-parameter">
                        <LineField
                          label={`Parameter for ${parameter}`}
                          value={line.parameter}
                          onChange={(value) => setRowField(key, defaults, "parameter", value)}
                        />
                      </td>
                      <td className="pdi-spec">
                        <LineField
                          label={`Specification for ${parameter}`}
                          value={line.specification}
                          onChange={(value) => setRowField(key, defaults, "specification", value)}
                        />
                      </td>
                      <td className="pdi-freq">
                        <LineField
                          label={`Frequency for ${parameter}`}
                          value={line.freq}
                          onChange={(value) => setRowField(key, defaults, "freq", value)}
                        />
                      </td>
                      <td className="pdi-method">
                        <LineField
                          label={`Inspection method for ${parameter}`}
                          value={line.method}
                          onChange={(value) => setRowField(key, defaults, "method", value)}
                        />
                      </td>
                      <td className="pdi-observation-cell">
                        <select
                          className={`pdi-observation${
                            line.observation === "OK"
                              ? " is-ok"
                              : line.observation === "NOT OK"
                                ? " is-not-ok"
                                : ""
                          }`}
                          aria-label={`Observation for ${parameter}`}
                          value={line.observation}
                          onChange={(event) =>
                            setRowField(key, defaults, "observation", event.target.value)
                          }
                        >
                          <option value="">Select</option>
                          {PDI_OBSERVATIONS.map((choice) => (
                            <option key={choice} value={choice}>
                              {choice}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="pdi-remark-cell">
                        <LineField
                          multiline
                          label={`Remarks for ${parameter}`}
                          value={line.remark}
                          onChange={(value) => setRowField(key, defaults, "remark", value)}
                        />
                      </td>
                    </tr>
                  )
                })}
              {reportSections.map((section, sectionIndex) =>
                section.items.map((item, itemIndex) => {
                  const key = pdiItemKey(sectionIndex, itemIndex)
                  const defaults = {
                    section: itemIndex === 0 ? section.title : "",
                    parameter: item.parameter,
                    specification: item.specification,
                    freq: item.freq,
                    method: item.method,
                    observation: "",
                    remark: "",
                  }
                  const line = rowValue(key, defaults)
                  return (
                    <tr key={key}>
                      {itemIndex === 0 && (
                        <td className="pdi-section" rowSpan={section.items.length}>
                          <LineField
                            label={`Section ${section.title}`}
                            value={line.section}
                            onChange={(value) => setRowField(key, defaults, "section", value)}
                          />
                        </td>
                      )}
                      <td className="pdi-parameter">
                        <LineField
                          label={`Parameter for ${item.parameter}`}
                          value={line.parameter}
                          onChange={(value) => setRowField(key, defaults, "parameter", value)}
                        />
                      </td>
                      <td className="pdi-spec">
                        <LineField
                          label={`Specification for ${item.parameter}`}
                          value={line.specification}
                          onChange={(value) => setRowField(key, defaults, "specification", value)}
                        />
                      </td>
                      <td className="pdi-freq">
                        <LineField
                          label={`Frequency for ${item.parameter}`}
                          value={line.freq}
                          onChange={(value) => setRowField(key, defaults, "freq", value)}
                        />
                      </td>
                      <td className="pdi-method">
                        <LineField
                          label={`Inspection method for ${item.parameter}`}
                          value={line.method}
                          onChange={(value) => setRowField(key, defaults, "method", value)}
                        />
                      </td>
                      <td className="pdi-observation-cell">
                        <select
                          className={`pdi-observation${
                            line.observation === "OK"
                              ? " is-ok"
                              : line.observation === "NOT OK"
                                ? " is-not-ok"
                                : ""
                          }`}
                          aria-label={`Observation for ${item.parameter}`}
                          value={line.observation}
                          onChange={(event) =>
                            setRowField(key, defaults, "observation", event.target.value)
                          }
                        >
                          <option value="">Select</option>
                          {PDI_OBSERVATIONS.map((choice) => (
                            <option key={choice} value={choice}>
                              {choice}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="pdi-remark-cell">
                        <LineField
                          multiline
                          label={`Remarks for ${item.parameter}`}
                          value={line.remark}
                          onChange={(value) => setRowField(key, defaults, "remark", value)}
                        />
                      </td>
                    </tr>
                  )
                }),
              )}
            </tbody>
          </table>
        </div>

        <div className="pdi-signoff">
          <label className="pdi-sign">
            <span>Checked by</span>
            <input value={checkedBy} onChange={(event) => setCheckedBy(event.target.value)} />
          </label>
          <label className="pdi-sign">
            <span>Approved by</span>
            <input value={approvedBy} onChange={(event) => setApprovedBy(event.target.value)} />
          </label>
        </div>
      </article>
    </div>
  )
}
