import { PDI_SECTIONS, clampFrequency } from "./pdi"

export const FORMAT_PART = "NBE-PDI-FORMAT"
const DELIM = " || "

function clean(value) {
  return String(value || "").split(DELIM).join(" ").trim()
}

export function sectionsToLines(sections) {
  return sections.flatMap((section) =>
    section.items.map((item) =>
      [
        clean(section.title),
        clean(item.parameter),
        clean(item.specification),
        String(clampFrequency(String(item.freq).replace("%", ""))),
        clean(item.method),
      ].join(DELIM),
    ),
  )
}

export function sectionsFromLines(lines) {
  const sections = []
  for (const raw of Array.isArray(lines) ? lines : []) {
    const parts = String(raw).split(DELIM)
    if (parts.length < 5) continue
    const [title, parameter, specification, frequency, ...methodParts] = parts
    const sectionTitle = title.trim()
    const name = parameter.trim()
    if (!sectionTitle || !name) continue
    let section = sections.find((item) => item.title === sectionTitle)
    if (!section) {
      section = { title: sectionTitle, items: [] }
      sections.push(section)
    }
    section.items.push({
      parameter: name,
      specification: specification.trim(),
      freq: `${clampFrequency(frequency)}%`,
      method: methodParts.join(DELIM).trim(),
    })
  }
  return sections
}

export function formatRecord(lines) {
  const sections = sectionsFromLines(lines)
  return sections.length ? sections : PDI_SECTIONS
}

export function visibleProducts(products) {
  return (Array.isArray(products) ? products : []).filter(
    (product) => product?.part_number !== FORMAT_PART,
  )
}
