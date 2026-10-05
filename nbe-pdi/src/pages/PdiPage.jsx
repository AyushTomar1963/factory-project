import { useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { fetchPdiProducts } from "../api/inspection"
import { PdiFormatEditor } from "../components/inspection/PdiFormatEditor"
import { usePdiFormat } from "../hooks/usePdiFormat"
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

function observationClass(value) {
  if (value === "OK") return "pdi-observation is-ok"
  if (value === "NOT OK") return "pdi-observation is-not-ok"
  return "pdi-observation"
}

function ObservationSelect({ label, value, onChange }) {
  return (
    <select
      className={observationClass(value)}
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">Select</option>
      {PDI_OBSERVATIONS.map((choice) => (
        <option key={choice} value={choice}>
          {choice}
        </option>
      ))}
    </select>
  )
}

function ReadOnlyValue({ value }) {
  return <span className="pdi-readonly">{value}</span>
}

function PhoneChecklist({ checklist, onField }) {
  const groups = []
  for (const entry of checklist) {
    const title = entry.showSection ? entry.line.section : ""
    const last = groups[groups.length - 1]
    if (!last || (title && title !== last.title)) groups.push({ title: title || last?.title || "", items: [] })
    groups[groups.length - 1].items.push(entry)
  }

  return (
    <div className="pdi-phone-list">
      {groups.map((group) => (
        <section key={group.title || group.items[0].key} className="pdi-phone-group">
          {group.title ? <h2 className="pdi-phone-section">{group.title}</h2> : null}
          {group.items.map((entry) => {
            const { key, defaults, line, label } = entry
            const facts = [line.freq, line.method].filter(Boolean).join(" · ")
            return (
              <article key={key} className="pdi-phone-card">
                <div className="pdi-phone-copy">
                  <h3 className="pdi-phone-title">{line.parameter}</h3>
                  {line.specification ? <p className="pdi-phone-spec">{line.specification}</p> : null}
                  {facts ? <p className="pdi-phone-facts">{facts}</p> : null}
                </div>
                <div className="pdi-phone-actions">
                  <ObservationSelect
                    label={`Observation for ${label}`}
                    value={line.observation}
                    onChange={(value) => onField(key, defaults, "observation", value)}
                  />
                  <input
                    className="pdi-cell-input"
                    aria-label={`Remarks for ${label}`}
                    placeholder="Remarks"
                    value={line.remark}
                    onChange={(event) => onField(key, defaults, "remark", event.target.value)}
                  />
                </div>
              </article>
            )
          })}
        </section>
      ))}
    </div>
  )
}

export function PdiPage({ embedded = false, layout, token, onLeave, onLogout, canEditFormat = false }) {
  const pdiFormat = usePdiFormat(token)
  const [params, setParams] = useSearchParams()
  const editingFormat = canEditFormat && params.get("edit") === "format"
  const [savingFormat, setSavingFormat] = useState(false)
  const [formatError, setFormatError] = useState("")
  const [meta, setMeta] = useState(initialMeta)
  const [rows, setRows] = useState({})
  const [checkedBy, setCheckedBy] = useState("")
  const [approvedBy, setApprovedBy] = useState("")
  const [products, setProducts] = useState([])
  const [productStatus, setProductStatus] = useState(token ? "loading" : "missing")

  const selectedProduct = products.find((product) => product.part_number === meta.partNo)
  const reportSections = pdiSectionsForProduct(selectedProduct?.parameters, pdiFormat.sections)
  const extraParameters = extraProductParameters(selectedProduct?.parameters, pdiFormat.sections)
  const metaRef = useRef(meta)
  useEffect(() => {
    metaRef.current = meta
  }, [meta])

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

  const checklist = []
  extraParameters.forEach((parameter, itemIndex) => {
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
    checklist.push({
      key,
      defaults,
      line: rowValue(key, defaults),
      showSection: itemIndex === 0,
      sectionSpan: extraParameters.length,
      label: parameter,
    })
  })
  reportSections.forEach((section, sectionIndex) => {
    section.items.forEach((item, itemIndex) => {
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
      checklist.push({
        key,
        defaults,
        line: rowValue(key, defaults),
        showSection: itemIndex === 0,
        sectionSpan: section.items.length,
        label: item.parameter,
      })
    })
  })

  const frame = layout || (embedded ? "embedded" : "page")

  const closeFormatEditor = () => {
    if (params.get("edit") !== "format") return
    if (window.history.state?.idx > 0) {
      window.history.back()
      return
    }
    const next = new URLSearchParams(params)
    next.delete("edit")
    setParams(next, { replace: true })
  }

  const openFormatEditor = () => {
    const next = new URLSearchParams(params)
    next.set("edit", "format")
    if (next.toString() === params.toString()) return
    setFormatError("")
    setParams(next)
    window.scrollTo({ top: 0, left: 0 })
  }

  return (
    <div className={`pdi-page${frame === "page" ? "" : ` pdi-page-${frame}`}`}>
      <div className="pdi-toolbar no-print">
        {frame === "page" && (
          <Link to="/" className="pdi-back-link">
            Back to portal
          </Link>
        )}
        {onLeave && (
          <button type="button" className="pdi-back-link" onClick={onLeave}>
            QC station
          </button>
        )}
        <div className="pdi-toolbar-actions">
          {onLogout && (
            <button type="button" className="pdi-back-link pdi-toolbar-logout" onClick={onLogout}>
              Sign out
            </button>
          )}
          {!editingFormat && (
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
          )}
        </div>
        {canEditFormat && !editingFormat && (
          <button type="button" className="pdi-format-button" onClick={openFormatEditor}>
            Edit format
          </button>
        )}
        <p className="pdi-source">
          {editingFormat && "Change the checklist, then save. Workers fill observation and remarks only."}
          {!editingFormat && productStatus === "loading" && "Loading product master…"}
          {!editingFormat && productStatus === "ready" &&
            (products.length
              ? "Part details come from Product Master. Fill the header, then mark observation and remarks."
              : "Product Master has no parts yet. Add one there first.")}
          {productStatus !== "loading" && productStatus !== "ready" && productStatus !== "missing" && productStatus}
          {formatError && ` ${formatError}`}
        </p>
      </div>

      {editingFormat ? (
        pdiFormat.ready ? (
        <PdiFormatEditor
          key={pdiFormat.sections.map((section) => section.items.map((item) => item.parameter).join(",")).join("|")}
          initial={pdiFormat.sections}
          saving={savingFormat}
          onCancel={closeFormatEditor}
          onSave={async (next) => {
            setSavingFormat(true)
            setFormatError("")
            try {
              await pdiFormat.save(next)
              closeFormatEditor()
            } catch (error) {
              setFormatError(error.message || "Could not save the format")
            } finally {
              setSavingFormat(false)
            }
          }}
        />
        ) : (
          <p className="pdi-source">Loading the format…</p>
        )
      ) : (
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
            <label key={field.key} className={field.key === "partNo" ? "pdi-field pdi-field-part" : "pdi-field"}>
              <span>{field.label}</span>
              {field.key === "partNo" ? (
                <select
                  aria-label="Part number from product master"
                  value={meta.partNo}
                  onChange={(event) => chooseProduct(event.target.value)}
                >
                  <option value="">Select from product master</option>
                  {products.map((product) => (
                    <option key={product.part_number} value={product.part_number}>
                      {product.part_number}
                      {product.part_name ? ` — ${product.part_name}` : ""}
                    </option>
                  ))}
                </select>
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
              {checklist.map((entry) => {
                const { key, defaults, line, showSection, sectionSpan, label } = entry
                return (
                  <tr key={key}>
                    {showSection && (
                      <td className="pdi-section" rowSpan={sectionSpan}>
                        <ReadOnlyValue value={line.section} />
                      </td>
                    )}
                    <td className="pdi-parameter">
                      <ReadOnlyValue value={line.parameter} />
                    </td>
                    <td className="pdi-spec">
                      <ReadOnlyValue value={line.specification} />
                    </td>
                    <td className="pdi-freq">
                      <ReadOnlyValue value={line.freq} />
                    </td>
                    <td className="pdi-method">
                      <ReadOnlyValue value={line.method} />
                    </td>
                    <td className="pdi-observation-cell">
                      <ObservationSelect
                        label={`Observation for ${label}`}
                        value={line.observation}
                        onChange={(value) => setRowField(key, defaults, "observation", value)}
                      />
                    </td>
                    <td className="pdi-remark-cell">
                      <textarea
                        className="pdi-cell-input pdi-line-remark"
                        rows={2}
                        aria-label={`Remarks for ${label}`}
                        value={line.remark}
                        onChange={(event) => setRowField(key, defaults, "remark", event.target.value)}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <PhoneChecklist checklist={checklist} onField={setRowField} />

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
      )}
    </div>
  )
}
