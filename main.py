from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import gspread
import datetime

app = FastAPI()

# Allow React to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Initialize Google Sheets (The Robot User)
# Ensure 'google_credentials.json' is in the same folder as this file!
try:
    gc = gspread.service_account(filename='google_credentials.json')
    
    # We are now using open_by_key with your EXACT spreadsheet ID!
    sh = gc.open_by_key("1eFMcq_pSOeOvz8-StfzFryOHN8Da9MsVL4nS_fGTAQE").sheet1 
    
    print("Successfully connected to the EXACT Google Sheet!")
except Exception as e:
    print(f"Failed to connect to Google Sheets: {e}")

# 2. Define the exact data React will send us
class InspectionRequest(BaseModel):
    part_name: str
    status: str  # 'GREEN', 'YELLOW', or 'RED'
    worker_remark: str | None = None

@app.get("/ping")
def ping_server():
    return {"message": "Hello from Python! Connected to Google Sheets (No AI yet)."}

@app.post("/api/log-inspection")
def log_inspection(request: InspectionRequest):
    
    # Since we are skipping AI for now, we just set these to N/A
    ai_category = "N/A (AI Disabled)"
    ai_report = "N/A (AI Disabled)"
    
    # Append the row directly to Google Sheets
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # This array represents columns A, B, C, D, E, F in your spreadsheet
        row_data = [
            timestamp, 
            request.part_name, 
            request.status, 
            request.worker_remark or "None", 
            ai_category, 
            ai_report
        ]
        
        sh.append_row(row_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write to Google Sheets: {str(e)}")

    return {"message": "Logged successfully to Google Sheets!"}