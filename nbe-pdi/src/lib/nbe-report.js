export const NBE_COMPANY = "NBE Motors Pvt. Ltd."
export const NBE_REPORT_CREDIT = "NBE Motors QA System"

function rewrite(value) {
  if (typeof value !== "string") return value
  return value
    .replace(/rushab industries qa system \(gemini ai\)/gi, NBE_REPORT_CREDIT)
    .replace(/rushab industries qa system/gi, NBE_REPORT_CREDIT)
    .replace(/rushab industries/gi, NBE_COMPANY)
    .replace(/\brushab\b/gi, "NBE Motors")
}

export function asNbeReport(report) {
  if (!report || typeof report !== "object") return report
  const sections = Array.isArray(report.sections)
    ? report.sections.map((section) => ({
        ...section,
        heading: rewrite(section?.heading),
        body: rewrite(section?.body),
      }))
    : report.sections
  const recommendations = Array.isArray(report.recommendations)
    ? report.recommendations.map(rewrite)
    : report.recommendations
  const reportId = typeof report.report_id === "string" ? report.report_id.replace(/^RIQ-/, "NBE-") : report.report_id

  return {
    ...report,
    report_id: reportId,
    company: NBE_COMPANY,
    title: rewrite(report.title),
    executive_summary: rewrite(report.executive_summary),
    sections,
    recommendations,
    generated_by: NBE_REPORT_CREDIT,
  }
}
