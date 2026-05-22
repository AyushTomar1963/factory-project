
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
import gspread
import datetime
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------
# 1. INITIALIZE GOOGLE SHEETS
# -----------------------------------------------------------------
try:
    gc = gspread.service_account(filename='google_credentials.json')
    SHEET_ID = os.getenv("SPREADSHEET_ID")
    spreadsheet = gc.open_by_key(SHEET_ID)
    
    log_sheet = spreadsheet.worksheet("Inspection_Logs")
    specs_sheet = spreadsheet.worksheet("Master_Specs")
    print("Connected to both Inspection_Logs and Master_Specs successfully!")

    expected_headers = ["Timestamp", "Part Number", "Part Name", "Stage", "Measurements", "Status", "Worker Remark", "AI Category", "AI Formal Report"]
    first_row = log_sheet.row_values(1)
    
    if first_row != expected_headers:
        print("Headers missing or outdated! Re-injecting correct headers...")
        if first_row:
            log_sheet.delete_rows(1)
        log_sheet.insert_row(expected_headers, 1)
        print("Headers corrected successfully.")

except Exception as e:
    print(f"Failed to connect to Google Sheets: {e}")

# -----------------------------------------------------------------
# 2. INITIALIZE AI BRAIN
# -----------------------------------------------------------------
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    print("WARNING: No Gemini API Key found in .env file!")

# -----------------------------------------------------------------
# 3. DATA STRUCTURES
# -----------------------------------------------------------------
class InspectionLogRequest(BaseModel):
    part_number: str
    part_name: str
    current_stage: str
    measured_values: Dict[str, str]  # values are now "GREEN", "YELLOW", or "RED"
    status: str                       # overall: "GREEN", "YELLOW", or "RED"
    worker_remark: Optional[str] = None

def clean(s: str) -> str:
    return ''.join(str(s).split())

@app.get("/ping")
def ping_server():
    return {"message": "Python API is Live and Master Specs are Ready!"}

@app.get("/api/debug")
def debug():
    try:
        raw = specs_sheet.get_all_values()
        return {"rows": raw[:3]}
    except Exception as e:
        return {"error": str(e)}

# -----------------------------------------------------------------
# 4. ENDPOINT: FETCH SPECS DYNAMICALLY
# -----------------------------------------------------------------
@app.get("/api/get-spec/{part_number}")
def get_spec(part_number: str):
    try:
        raw = specs_sheet.get_all_values()
        rows = raw[1:]

        for row in rows:
            if len(row) < 4:
                continue

            sheet_code = clean(row[3])
            incoming_code = clean(part_number)

            if sheet_code == incoming_code:
                raw_params = []
                for idx in [5, 8, 11, 14]:
                    if idx < len(row):
                        val = row[idx].strip()
                        if val and val != "-":
                            raw_params.append(val)

                return {
                    "found": True,
                    "part_number": sheet_code,
                    "part_name": row[2].strip(),
                    "group": row[1].strip(),
                    "parameters": raw_params
                }

        raise HTTPException(status_code=404, detail="Part Code not found in Master Specs!")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------
# 5. ENDPOINT: LOG INSPECTION & WORKFLOW VALIDATION
# -----------------------------------------------------------------
@app.post("/api/log-inspection")
def log_inspection(request: InspectionLogRequest):

    # --- STAGE GATEKEEPER ---
    # Only GREEN passes to next stage. YELLOW and RED both block progression.
    try:
        all_logs = log_sheet.get_all_records()

        if request.current_stage == "Stage 2":
            stage1_passed = any(
                clean(str(r.get("Part Number", ""))) == clean(request.part_number) and
                r.get("Stage") == "Stage 1" and
                r.get("Status") == "GREEN"
                for r in all_logs
            )
            if not stage1_passed:
                raise HTTPException(
                    status_code=400,
                    detail="BLOCKED: Stage 1 must be fully PASSED (GREEN) before Stage 2!"
                )

        elif request.current_stage == "Stage 3":
            stage2_passed = any(
                clean(str(r.get("Part Number", ""))) == clean(request.part_number) and
                r.get("Stage") == "Stage 2" and
                r.get("Status") == "GREEN"
                for r in all_logs
            )
            if not stage2_passed:
                raise HTTPException(
                    status_code=400,
                    detail="BLOCKED: Stage 2 must be fully PASSED (GREEN) before Stage 3!"
                )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail="History verification failed.")

    # --- AI CATEGORIZATION ---
    # Triggers on RED (fail) and YELLOW (send to boss) — not on GREEN
    ai_category = "N/A"
    ai_report = "N/A"

    if request.status in ("RED", "YELLOW") and GEMINI_KEY:
        measurements_str = ", ".join([f"{k}: {v}" for k, v in request.measured_values.items()])
        
        if request.status == "RED":
            situation = "The part has been REJECTED (hard fail)."
        else:
            situation = "The part has been flagged as MARGINAL and escalated to the supervisor."

        prompt = f"""
        You are a factory Quality Assurance assistant.
        Part '{request.part_name}' was inspected at '{request.current_stage}'.
        Situation: {situation}
        Parameter ratings: {measurements_str}
        Worker remark: '{request.worker_remark or "None provided"}'

        1. Categorize the issue in 1-3 words (e.g., 'Dimensional Error', 'Marginal Fit', 'Physical Damage').
        2. Write a short formal English report (1 sentence max) for management.

        Format EXACTLY like this:
        [CATEGORY] | [REPORT]
        """
        try:
            response = model.generate_content(prompt)
            parts = response.text.split("|")
            if len(parts) >= 2:
                ai_category = parts[0].strip()
                ai_report = parts[1].strip()
            else:
                ai_report = response.text.strip()
        except Exception as e:
            print(f"AI generation failed: {e}")
            ai_report = f"AI Error: {str(e)}"

    # --- SAVE TO GOOGLE SHEETS ---
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Format: "ID(17H7): GREEN | OD(39.98-40.02mm): RED | TL: YELLOW"
        formatted_measurements = " | ".join([f"{k}: {v}" for k, v in request.measured_values.items()])

        row_data = [
            timestamp,
            request.part_number,
            request.part_name,
            request.current_stage,
            formatted_measurements,
            request.status,
            request.worker_remark or "None",
            ai_category,
            ai_report
        ]

        log_sheet.append_row(row_data)
        return {"message": f"Successfully logged {request.current_stage} for {request.part_number}!"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write to Google Sheets: {str(e)}")