export const PDI_COMPANY = "NBE MOTORS PRIVATE LIMITED"
export const PDI_TITLE = "PRE DISPATCH INSPECTION REPORT"

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
    { key: "invoiceDate", label: "INVOICE DATE" },
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
        "",
        "TEST Bed",
      ],
      [
        "Full Load Test to determine Efficiency, Power Factor and Slip",
        "One Motors of each type & design, manufactured in three months",
        "",
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
      ["VARNISH Make of Varnish", "", "Batch", "As per validation"],
      [
        "Fitment of Fan Cover, bolts, studs, nuts, Eye bolts, lugs, plugs, flanges",
        "",
        "100%",
        "VISUAL",
      ],
      ["EARTH PLATE", "", "BATCH", "VISUAL"],
    ],
  },
  {
    title: "4. PAINTING VERIFICATION",
    items: [
      ["PAINT COLOR SHADE Casting-Std", "", "100%", "Approved TEMPLATE"],
      ["CED Coating thickness", "20 to 40 Micron", "", "DFT meter"],
      ["Free from VISUAL DEFECTS (Painting-damage, rust etc)", "", "100%", "VISUAL"],
    ],
  },
  {
    title: "5. FINAL PRODUCT VERIFICATION",
    items: [
      ["DIRECTION OF ROTATION", "", "100%", "VISUAL"],
      ["NAME PLATE MODEL DETAILS", "", "100%", "VISUAL"],
      [
        "KIRLOSKAR NAME & ADDRESS VERIFICATION No Spelling mistake & legibility issue",
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
      ["NET WEIGHT", "", "ACTUAL", "ACTUAL-Value to be mentioned in Kg"],
      ["GROSS WEIGHT", "", "ACTUAL", "ACTUAL-Value to be mentioned in Kg"],
      [
        "Material test report for all Casting parts & Forging parts",
        "",
        "Per Heat/Batch Code",
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
