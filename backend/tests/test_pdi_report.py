import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_pdi_report.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_pdi_report", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pdi_workbook_matches_template_spec():
    generator = load_generator()
    wb = generator.build_workbook()
    ws = wb["PDI Report"]

    assert ws["A1"].value == "NBE MOTORS PRIVATE LIMITED"
    assert ws["A1"].font.bold is True
    assert ws["A1"].font.size == 16
    assert ws["A1"].font.color.rgb.endswith("1F4E78")
    assert ws["A1"].alignment.horizontal == "center"
    assert "A1:F1" in [str(item) for item in ws.merged_cells.ranges]

    assert ws["A2"].value == "PRE DISPATCH INSPECTION REPORT"
    assert ws["A2"].font.bold is True
    assert ws["A2"].font.size == 11
    assert ws["A2"].alignment.horizontal == "center"

    assert ws["A4"].value == "REV NO / DATE"
    assert ws["B4"].value == "01/04/2025"
    assert ws["D4"].value == "PART NO"
    assert ws["A5"].value == "PART DESCRIPTION"
    assert ws["D5"].value == "HP/KW"
    assert ws["A6"].value == "CUSTOMER NAME"
    assert ws["D6"].value == "PUMP PIPE SIZE"
    assert ws["A7"].value == "NAME PLATE SERIAL NUMBER"
    assert ws["D7"].value == "BATCH NO"
    assert ws["A8"].value == "INVOICE NO"
    assert ws["D8"].value == "PO NO"
    assert ws["A9"].value == "INVOICE DATE"
    assert ws["D9"].value == "PO QTY"

    headers = [ws.cell(11, col).value for col in range(1, 7)]
    assert headers == [
        "SR NO",
        "PARAMETER",
        "SPECIFICATION",
        "FREQ",
        "INSPECTION METHOD",
        "OBSERVATION",
    ]
    assert ws["A11"].font.bold is True
    assert ws["A11"].font.color.rgb.endswith("FFFFFF")
    assert ws["A11"].fill.fgColor.rgb.endswith("1F4E78")

    assert [ws.column_dimensions[letter].width for letter in "ABCDEF"] == [18, 45, 30, 15, 28, 18]

    parameters = []
    row = 12
    while ws.cell(row, 2).value:
        parameters.append(
            (
                ws.cell(row, 2).value,
                ws.cell(row, 3).value,
                ws.cell(row, 4).value,
                ws.cell(row, 5).value,
            )
        )
        assert ws.cell(row, 2).alignment.wrap_text is True
        assert ws.cell(row, 1).border.left.style == "thin"
        row += 1
    last_data_row = row - 1

    assert parameters[0] == ("Insulation Resistance Test", "", "100%", "TEST Bed")
    assert parameters[8][0] == "Temperature Rise Test"
    assert parameters[8][1] == "One Motors of each type & design, manufactured in three months"
    assert parameters[8][2] in ("", None)
    assert parameters[9][0] == "Full Load Test to determine Efficiency, Power Factor and Slip"
    assert ("MOTOR ROTATION", "", "100%", "VISUAL") in parameters
    assert ("CED Coating thickness", "20 to 40 Micron", None, "DFT meter") in [
        (name, spec or None, freq or None, method) for name, spec, freq, method in parameters
    ]
    assert parameters[-1][0] == "Material test report for all Casting parts & Forging parts"
    assert parameters[-1][2] == "Per Heat/Batch Code"
    assert len(parameters) == 39

    merged = {str(item) for item in ws.merged_cells.ranges}
    assert "A12:A21" in merged
    assert "A22:A22" not in merged
    assert ws["A12"].value == "1. ELECTRICAL TESTING CONFIRMATION"
    assert ws["A22"].value == "2. COOLING FAN COVER POSITION"
    assert ws["A12"].alignment.wrap_text is True

    zebra_row = 13
    assert ws.cell(zebra_row, 2).fill.fgColor.rgb.endswith("F9FAFB")
    assert ws.cell(12, 2).fill.fgColor.rgb.endswith("FFFFFF")

    validations = list(ws.data_validations.dataValidation)
    assert len(validations) == 1
    rule = validations[0]
    assert rule.type == "list"
    assert rule.formula1 == '"OK,NOT OK"'
    assert rule.allow_blank is True
    assert rule.showErrorMessage is True
    assert rule.errorStyle == "stop"
    assert rule.errorTitle == "Invalid Entry"
    assert rule.error == "Please select OK or NOT OK from the dropdown list."
    assert str(rule.sqref) == f"F12:F{last_data_row}"

    remarks_row = None
    signoff_row = None
    for scan in range(last_data_row + 1, last_data_row + 12):
        if ws.cell(scan, 1).value == "Remarks":
            remarks_row = scan
        if ws.cell(scan, 1).value == "Checked by: _____________":
            signoff_row = scan
    assert remarks_row is not None
    assert f"A{remarks_row}:F{remarks_row}" in merged
    assert signoff_row is not None
    assert ws.cell(signoff_row, 4).value == "Approved by: _____________"
    assert f"A{signoff_row}:C{signoff_row}" in merged
    assert f"D{signoff_row}:F{signoff_row}" in merged
