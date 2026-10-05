import { useState } from "react"
import { PDI_SECTIONS, clampFrequency } from "../../pdi"
import { Button } from "../ui/qa-button"

function blankLine() {
  return { parameter: "", specification: "", freq: "100%", method: "" }
}

export function PdiFormatEditor({ initial, onSave, onCancel, saving }) {
  const [sections, setSections] = useState(initial)
  const [error, setError] = useState("")

  const updateSection = (index, patch) => {
    setSections((current) =>
      current.map((section, sectionIndex) =>
        sectionIndex === index ? { ...section, ...patch } : section,
      ),
    )
  }

  const updateLine = (sectionIndex, lineIndex, patch) => {
    setSections((current) =>
      current.map((section, index) => {
        if (index !== sectionIndex) return section
        return {
          ...section,
          items: section.items.map((item, itemIndex) =>
            itemIndex === lineIndex ? { ...item, ...patch } : item,
          ),
        }
      }),
    )
  }

  const moveLine = (sectionIndex, lineIndex, direction) => {
    setSections((current) =>
      current.map((section, index) => {
        if (index !== sectionIndex) return section
        const nextIndex = lineIndex + direction
        if (nextIndex < 0 || nextIndex >= section.items.length) return section
        const items = [...section.items]
        const [line] = items.splice(lineIndex, 1)
        items.splice(nextIndex, 0, line)
        return { ...section, items }
      }),
    )
  }

  const save = async () => {
    const names = new Set()
    const cleaned = []
    for (const section of sections) {
      const title = section.title.trim()
      if (!title) {
        setError("Every section needs a title.")
        return
      }
      const items = []
      for (const item of section.items) {
        const parameter = item.parameter.trim()
        if (!parameter) {
          setError(`Add a parameter in ${title}, or remove the empty line.`)
          return
        }
        const key = parameter.toLowerCase()
        if (names.has(key)) {
          setError(`"${parameter}" is on the format more than once.`)
          return
        }
        names.add(key)
        items.push({
          parameter,
          specification: item.specification.trim(),
          freq: `${clampFrequency(String(item.freq).replace("%", ""))}%`,
          method: item.method.trim(),
        })
      }
      if (items.length) cleaned.push({ title, items })
    }
    if (!cleaned.length) {
      setError("Keep at least one checklist line.")
      return
    }
    setError("")
    await onSave(cleaned)
  }

  return (
    <div className="pdi-format-editor">
      <div className="pdi-format-editor-bar">
        <button type="button" className="pdi-back-link" onClick={onCancel}>
          Back to checklist
        </button>
        <button
          type="button"
          className="pdi-back-link"
          onClick={() => setSections(PDI_SECTIONS.map((section) => ({
            title: section.title,
            items: section.items.map((item) => ({ ...item })),
          })))}
        >
          Restore standard lines
        </button>
      </div>
      <p className="pdi-source">
        Change the sections, checks, specifications, frequency, and method. Workers fill this checklist and cannot change the format.
      </p>
      {sections.map((section, sectionIndex) => (
        <section key={`${section.title}-${sectionIndex}`} className="pdi-format-section">
          <label className="pdi-format-field">
            <span>Section</span>
            <input
              value={section.title}
              aria-label={`Section ${sectionIndex + 1}`}
              onChange={(event) => updateSection(sectionIndex, { title: event.target.value })}
            />
          </label>
          <ul>
            {section.items.map((item, lineIndex) => (
              <li key={`${sectionIndex}-${lineIndex}`} className="pdi-format-line">
                <label className="pdi-format-field">
                  <span>Parameter</span>
                  <input
                    value={item.parameter}
                    aria-label={`Parameter ${sectionIndex + 1}.${lineIndex + 1}`}
                    onChange={(event) => updateLine(sectionIndex, lineIndex, { parameter: event.target.value })}
                  />
                </label>
                <label className="pdi-format-field">
                  <span>Specification</span>
                  <input
                    value={item.specification}
                    aria-label={`Specification ${sectionIndex + 1}.${lineIndex + 1}`}
                    onChange={(event) =>
                      updateLine(sectionIndex, lineIndex, { specification: event.target.value })
                    }
                  />
                </label>
                <label className="pdi-format-field pdi-format-freq">
                  <span>Frequency %</span>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    step={1}
                    inputMode="numeric"
                    aria-label={`Frequency percent ${sectionIndex + 1}.${lineIndex + 1}`}
                    value={String(item.freq).replace("%", "")}
                    onChange={(event) => updateLine(sectionIndex, lineIndex, { freq: event.target.value })}
                    onBlur={() =>
                      updateLine(sectionIndex, lineIndex, {
                        freq: `${clampFrequency(String(item.freq).replace("%", ""))}%`,
                      })
                    }
                  />
                </label>
                <label className="pdi-format-field">
                  <span>Method</span>
                  <input
                    value={item.method}
                    aria-label={`Method ${sectionIndex + 1}.${lineIndex + 1}`}
                    onChange={(event) => updateLine(sectionIndex, lineIndex, { method: event.target.value })}
                  />
                </label>
                <div className="pdi-format-line-actions">
                  <button type="button" onClick={() => moveLine(sectionIndex, lineIndex, -1)} disabled={lineIndex === 0}>
                    Up
                  </button>
                  <button
                    type="button"
                    onClick={() => moveLine(sectionIndex, lineIndex, 1)}
                    disabled={lineIndex === section.items.length - 1}
                  >
                    Down
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      updateSection(sectionIndex, {
                        items: section.items.filter((_, index) => index !== lineIndex),
                      })
                    }
                  >
                    Remove line
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <div className="pdi-format-line-actions">
            <button
              type="button"
              onClick={() => updateSection(sectionIndex, { items: [...section.items, blankLine()] })}
            >
              Add line
            </button>
            <button
              type="button"
              onClick={() => setSections((current) => current.filter((_, index) => index !== sectionIndex))}
            >
              Remove section
            </button>
          </div>
        </section>
      ))}
      <button
        type="button"
        className="pdi-format-add"
        onClick={() => setSections((current) => [...current, { title: "", items: [blankLine()] }])}
      >
        Add section
      </button>
      {error && <p className="pdi-format-error">{error}</p>}
      <div className="pdi-format-editor-bar">
        <Button type="button" variant="gradient" size="sm" disabled={saving} onClick={save}>
          {saving ? "Saving..." : "Save format"}
        </Button>
        <Button type="button" variant="muted" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
