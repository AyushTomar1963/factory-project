export const PDI_COMPANY = "NBE MOTORS PRIVATE LIMITED"
export const PDI_TITLE = "PRE DISPATCH INSPECTION REPORT"
export const COMPANY_ADDRESS_PARAMETER =
  "COMPANY NAME & ADDRESS VERIFICATION No Spelling mistake & legibility issue"

export const PDI_METADATA_ROWS = [
  [
    { key: "revNoDate", label: "REV NO / DATE", defaultValue: "01/04/2025" },
    { key: "partNo", label: "PART NO" },
  ],
  [
    { key: "partDescription", label: "PART DESCRIPTION" },
    { key: "hpKw", label: "HP/KW" },
  ],
  [
    { key: "customerName", label: "CUSTOMER NAME" },
    { key: "pumpPipeSize", label: "PUMP PIPE SIZE" },
  ],
  [
    { key: "namePlateSerial", label: "NAME PLATE SERIAL NUMBER" },
    { key: "batchNo", label: "BATCH NO" },
  ],
  [
    { key: "invoiceNo", label: "INVOICE NO" },
    { key: "poNo", label: "PO NO" },
  ],
  [
    { key: "invoiceDate", label: "INVOICE DATE", calendar: true },
    { key: "poQty", label: "PO QTY" },
  ],
]

export const PDI_OBSERVATIONS = ["OK", "NOT OK"]

export const PDI_SECTIONS = [
  {
    title: "1. ELECTRICAL TESTING CONFIRMATION",
    items: [
      ["Insulation Resistance Test", "", "100%", "TEST Bed"],
      ["Measurement of Resistance of Windings of Stator", "", "100%", "TEST Bed"],
      ["No Load Test", "", "100%", "TEST Bed"],
      ["High Voltage Test", "", "100%", "TEST Bed"],
      [
        "Locked Rotor Readings of Voltage, Current and Power Input at a suitable reduced voltage",
        "",
        "100%",
        "TEST Bed",
      ],
      ["Dimensions", "", "100%", "TEST Bed"],
      ["Earthing", "", "100%", "TEST Bed"],
      ["Terminal Marking", "", "100%", "TEST Bed"],
      [
        "Temperature Rise Test",
        "One Motors of each type & design, manufactured in three months",
        "100%",
        "TEST Bed",
      ],
      [
        "Full Load Test to determine Efficiency, Power Factor and Slip",
        "One Motors of each type & design, manufactured in three months",
        "100%",
        "TEST Bed",
      ],
    ],
  },
  {
    title: "2. COOLING FAN COVER POSITION",
    items: [["MOTOR ROTATION", "", "100%", "VISUAL"]],
  },
  {
    title: "3. VERIFICATION ASSEMBLY",
    items: [
      ["FRAME SIZE", "", "100%", "REF. CHART"],
      ["BEARING Make & SIZE", "", "100%", "As per validation"],
      ["VARNISH Make of Varnish", "Batch", "100%", "As per validation"],
      [
        "Fitment of Fan Cover, bolts, studs, nuts, Eye bolts, lugs, plugs, flanges",
        "",
        "100%",
        "VISUAL",
      ],
      ["EARTH PLATE", "BATCH", "100%", "VISUAL"],
    ],
  },
  {
    title: "4. PAINTING VERIFICATION",
    items: [
      ["PAINT COLOR SHADE Casting-Std", "", "100%", "Approved TEMPLATE"],
      ["CED Coating thickness", "20 to 40 Micron", "100%", "DFT meter"],
      ["Free from VISUAL DEFECTS (Painting-damage, rust etc)", "", "100%", "VISUAL"],
    ],
  },
  {
    title: "5. FINAL PRODUCT VERIFICATION",
    items: [
      ["DIRECTION OF ROTATION", "", "100%", "VISUAL"],
      ["NAME PLATE MODEL DETAILS", "", "100%", "VISUAL"],
      [
        COMPANY_ADDRESS_PARAMETER,
        "",
        "100%",
        "VISUAL",
      ],
      ["All over body of dents, damages, dirt, rust & scratch Free", "", "100%", "VISUAL"],
      ["BRAND LOGO AVAILABLE ON MOTORS", "", "100%", "VISUAL"],
      [
        "BRAND LOGO APPEARANCE - Damage/broken, excess shot blasting, legibility issue not allowed. Fan cover bolt plating to be ensured",
        "",
        "100%",
        "VISUAL",
      ],
      [
        "MOTOR BODY CASTING - No fin mismatch, No sand drop between fins, Mounting hole burr not allowed.",
        "",
        "100%",
        "VISUAL",
      ],
      [
        "CASTING FINISH - Blow hole, cold shut, crack, Sand Drop & Poor shot blasting not allowed",
        "",
        "100%",
        "VISUAL",
      ],
      ["Rear side Water Removal Pressurised Air", "", "100%", "VISUAL"],
      [
        "Sound Testing for Pump Body and Volute (sound testing-free hang the casting & bang by steel rod)",
        "",
        "100%",
        "VISUAL",
      ],
      ["Terminal Box Cover as per Brand LOGO", "", "100%", "VISUAL"],
    ],
  },
  {
    title: "6. PACKAGING",
    items: [
      ["WARRANTY CARD", "", "100%", "VISUAL"],
      ["INSTRUCTION MANUAL", "", "100%", "VISUAL"],
      ["OUTER BOX MRP DETAILS", "", "100%", "VISUAL"],
      ["MASTER BOX PLY", "", "100%", "No. of Ply"],
      ["INNER POLYTHENE COVER PROPERLY SEALED / NO OPEN END", "", "100%", "VISUAL"],
      ["PART NUMBER VERIFICATION", "", "100%", "VISUAL COMPARE WITH PO"],
      ["NET WEIGHT", "", "100%", "ACTUAL-Value to be mentioned in Kg"],
      ["GROSS WEIGHT", "", "100%", "ACTUAL-Value to be mentioned in Kg"],
      [
        "Material test report for all Casting parts & Forging parts",
        "Per Heat/Batch Code",
        "100%",
        "Attach actual test report as per Material Grade",
      ],
    ],
  },
].map((section) => ({
  title: section.title,
  items: section.items.map(([parameter, specification, freq, method]) => ({
    parameter,
    specification,
    freq,
    method,
  })),
}))

export function pdiItemKey(sectionIndex, itemIndex) {
  return `${sectionIndex}-${itemIndex}`
}

export function pdiTemplateParameters() {
  return PDI_SECTIONS.flatMap((section) => section.items.map((item) => item.parameter))
}

const PDI_TEMPLATE_NAMES = new Set(pdiTemplateParameters())
const STORED_FREQUENCY = /^(.*) \(([1-9]\d?|100)%\)$/

export function clampFrequency(value) {
  if (value === "" || value == null) return 100
  const number = Math.round(Number(value))
  if (!Number.isFinite(number)) return 100
  return Math.min(100, Math.max(1, number))
}

export function templateNames(sections = PDI_SECTIONS) {
  return sections.flatMap((section) => section.items.map((item) => item.parameter))
}

export function templateFrequency(parameter, sections = PDI_SECTIONS) {
  for (const section of sections) {
    const item = section.items.find((entry) => entry.parameter === parameter)
    if (!item) continue
    const match = String(item.freq).match(/^(\d+)\s*%$/)
    if (!match) return 100
    return clampFrequency(match[1])
  }
  return 100
}

export function readStoredParameter(raw) {
  const text = String(raw ?? "").trim()
  const match = text.match(STORED_FREQUENCY)
  let name = match ? match[1] : text
  const frequency = match ? Number(match[2]) : null
  if (name.includes("NAME & ADDRESS VERIFICATION") && name !== COMPANY_ADDRESS_PARAMETER) {
    name = COMPANY_ADDRESS_PARAMETER
  }
  return { name, frequency }
}

export function isPdiTemplateParameter(name, sections = PDI_SECTIONS) {
  const bare = readStoredParameter(name).name
  return PDI_TEMPLATE_NAMES.has(bare) || templateNames(sections).includes(bare)
}

export function templateSelection(parameters, sections = PDI_SECTIONS) {
  const names = new Set(templateNames(sections))
  const checks = []
  const frequencies = {}
  for (const raw of Array.isArray(parameters) ? parameters : []) {
    const { name, frequency } = readStoredParameter(raw)
    if (!names.has(name) || checks.includes(name)) continue
    checks.push(name)
    if (frequency) frequencies[name] = frequency
  }
  return { checks, frequencies }
}

export function parameterForStorage(name, frequency, sections = PDI_SECTIONS) {
  const chosen = clampFrequency(frequency)
  if (chosen === templateFrequency(name, sections)) return name
  return `${name} (${chosen}%)`
}

function sectionsWithFrequency(sections, frequencies) {
  return sections.map((section) => ({
    ...section,
    items: section.items.map((item) => {
      const chosen = frequencies?.get(item.parameter)
      if (!chosen) return { ...item, freq: item.freq || "100%" }
      return { ...item, freq: `${chosen}%` }
    }),
  }))
}

export function pdiSectionsForProduct(parameters, sections = PDI_SECTIONS) {
  const names = new Set(templateNames(sections))
  const saved = Array.isArray(parameters) ? parameters : []
  const included = saved.map(readStoredParameter).filter((item) => names.has(item.name))
  if (!included.length) {
    const hadTemplateLine = saved.some((raw) => PDI_TEMPLATE_NAMES.has(readStoredParameter(raw).name))
    return hadTemplateLine ? [] : sectionsWithFrequency(sections)
  }
  const frequencies = new Map()
  for (const item of included) {
    if (!frequencies.has(item.name)) frequencies.set(item.name, item.frequency)
  }
  return sectionsWithFrequency(
    sections
      .map((section) => ({
        ...section,
        items: section.items.filter((item) => frequencies.has(item.parameter)),
      }))
      .filter((section) => section.items.length),
    frequencies,
  )
}

export function extraProductParameters(parameters, sections = PDI_SECTIONS) {
  const names = new Set([...PDI_TEMPLATE_NAMES, ...templateNames(sections)])
  const saved = Array.isArray(parameters) ? parameters : []
  return saved
    .map(readStoredParameter)
    .filter((item) => !names.has(item.name))
    .map((item) => item.name)
}
