import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { fetchProducts } from "../api/admin"
import {
  PDI_COMPANY,
  PDI_METADATA_ROWS,
  PDI_OBSERVATIONS,
  PDI_SECTIONS,
  PDI_TITLE,
  pdiItemKey,
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

function mountPdiPrintHost() {
  const source = document.getElementById("pdi-report")
  if (!source) return

  syncControlValues(source)
  document.getElementById(PRINT_HOST_ID)?.remove()

  const host = document.createElement("div")
  host.id = PRINT_HOST_ID
  host.setAttribute("aria-hidden", "true")
  const clone = source.cloneNode(true)

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

export function PdiPage({ embedded = false, token }) {
  const [meta, setMeta] = useState(initialMeta)
  const [observations, setObservations] = useState({})
  const [remarks, setRemarks] = useState("")
  const [checkedBy, setCheckedBy] = useState("")
  const [approvedBy, setApprovedBy] = useState("")
  const [products, setProducts] = useState([])
  const [productStatus, setProductStatus] = useState(token ? "loading" : "missing")

  const selectedProduct = products.find((product) => product.part_number === meta.partNo)

  useEffect(() => {
    if (!token) return undefined
    let cancelled = false
    fetchProducts(token)
      .then((rows) => {
        if (cancelled) return
        setProducts(Array.isArray(rows) ? rows : [])
        setProductStatus("ready")
      })
      .catch((error) => {
        if (cancelled) return
        setProductStatus(error.message || "Could not load product master")
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
      partDescription: product?.part_name || "",
    }))
    setObservations((current) => {
      const next = { ...current }
      Object.keys(next).forEach((key) => {
        if (key.startsWith("master-")) delete next[key]
      })
      return next
    })
  }

  useEffect(() => {
    const onBeforePrint = () => mountPdiPrintHost()
    const onAfterPrint = () => removePdiPrintHost()
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
        <p className="pdi-source">
          {productStatus === "loading" && "Loading product master…"}
          {productStatus === "ready" &&
            (products.length
              ? "Part number, description, and parameters come from Product Master."
              : "Product Master has no parts yet. Add one there first.")}
          {productStatus !== "loading" && productStatus !== "ready" && productStatus !== "missing" && productStatus}
        </p>
        <button
          type="button"
          className="pdi-print-button"
          onClick={() => {
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
                  value={meta[field.key]}
                  readOnly={field.key === "partDescription"}
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
              </tr>
            </thead>
            <tbody>
              {selectedProduct?.parameters?.length > 0 &&
                selectedProduct.parameters.map((parameter, itemIndex) => {
                  const key = masterKey(itemIndex)
                  const observation = observations[key] || ""
                  return (
                    <tr key={key}>
                      {itemIndex === 0 && (
                        <td className="pdi-section" rowSpan={selectedProduct.parameters.length}>
                          {selectedProduct.group
                            ? `Product master · ${selectedProduct.group}`
                            : "Product master"}
                        </td>
                      )}
                      <td className="pdi-parameter">{parameter}</td>
                      <td className="pdi-spec"></td>
                      <td className="pdi-freq">100%</td>
                      <td className="pdi-method">Product master</td>
                      <td className="pdi-observation-cell">
                        <select
                          className={`pdi-observation${
                            observation === "OK"
                              ? " is-ok"
                              : observation === "NOT OK"
                                ? " is-not-ok"
                                : ""
                          }`}
                          aria-label={`Observation for ${parameter}`}
                          value={observation}
                          onChange={(event) =>
                            setObservations((current) => ({
                              ...current,
                              [key]: event.target.value,
                            }))
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
                    </tr>
                  )
                })}
              {PDI_SECTIONS.map((section, sectionIndex) =>
                section.items.map((item, itemIndex) => {
                  const key = pdiItemKey(sectionIndex, itemIndex)
                  const observation = observations[key] || ""
                  return (
                    <tr key={key}>
                      {itemIndex === 0 && (
                        <td className="pdi-section" rowSpan={section.items.length}>
                          {section.title}
                        </td>
                      )}
                      <td className="pdi-parameter">{item.parameter}</td>
                      <td className="pdi-spec">{item.specification}</td>
                      <td className="pdi-freq">{item.freq}</td>
                      <td className="pdi-method">{item.method}</td>
                      <td className="pdi-observation-cell">
                        <select
                          className={`pdi-observation${
                            observation === "OK"
                              ? " is-ok"
                              : observation === "NOT OK"
                                ? " is-not-ok"
                                : ""
                          }`}
                          aria-label={`Observation for ${item.parameter}`}
                          value={observation}
                          onChange={(event) =>
                            setObservations((current) => ({
                              ...current,
                              [key]: event.target.value,
                            }))
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
                    </tr>
                  )
                }),
              )}
            </tbody>
          </table>
        </div>

        <label className="pdi-remarks">
          <span>Remarks</span>
          <textarea value={remarks} onChange={(event) => setRemarks(event.target.value)} />
        </label>

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
