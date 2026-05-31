# from fastapi import FastAPI, HTTPException, Depends, status
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import Dict, Optional
# from datetime import datetime, timedelta, timezone
# import gspread
# import os
# import jwt
# import bcrypt
# import google.generativeai as genai
# from dotenv import load_dotenv

# load_dotenv()

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # -----------------------------------------------------------------
# # 1. SECURITY CONFIGURATION
# # -----------------------------------------------------------------
# SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-secret-key-change-in-production")
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8-hour shift

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     try:
#         return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
#     except Exception:
#         return False

# def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
#     to_encode = data.copy()
#     expire = datetime.now(timezone.utc) + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# def get_current_user(token: str = Depends(oauth2_scheme)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         role: str = payload.get("role")
#         sheet_id: str = payload.get("sheet_id")
#         if username is None or role is None:
#             raise credentials_exception
#         return {"username": username, "role": role, "sheet_id": sheet_id}
#     except jwt.PyJWTError:
#         raise credentials_exception

# def require_admin(current_user: dict = Depends(get_current_user)):
#     if current_user.get("role") != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Access denied: Admin privileges required."
#         )
#     return current_user

# # -----------------------------------------------------------------
# # 2. INITIALIZE GOOGLE SHEETS & AI
# # -----------------------------------------------------------------
# try:
#     gc = gspread.service_account(filename='google_credentials.json')
#     print("Connected to Google Service Account successfully!")
# except Exception as e:
#     print(f"Failed to connect to Google Service Account: {e}")

# GEMINI_KEY = os.getenv("GEMINI_API_KEY")
# if GEMINI_KEY:
#     genai.configure(api_key=GEMINI_KEY)
#     model = genai.GenerativeModel('gemini-2.5-flash')
# else:
#     print("WARNING: No Gemini API Key found in .env file!")

# # -----------------------------------------------------------------
# # 3. DATA STRUCTURES
# # -----------------------------------------------------------------
# class InspectionLogRequest(BaseModel):
#     sheet_id: str
#     part_number: str
#     part_name: str
#     current_stage: str
#     measured_values: Dict[str, str]
#     status: str
#     worker_remark: Optional[str] = None

# def clean(s: str) -> str:
#     return ''.join(str(s).split())

# @app.get("/ping")
# def ping_server():
#     return {"message": "Python API is Live and Secure!"}

# # -----------------------------------------------------------------
# # 4. AUTHENTICATION ENDPOINT
# # -----------------------------------------------------------------
# @app.post("/api/auth/login")
# def login(
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     sheet_id: str = "" 
# ):
#     print("\n" + "="*40)
#     print("🕵️ AUTHENTICATION DIAGNOSTIC STARTED")
#     print(f"1. Target Sheet ID: '{sheet_id}'")
#     print(f"2. Input Username: '{form_data.username}'")
    
#     if not sheet_id:
#         raise HTTPException(status_code=400, detail="sheet_id query parameter is required")
        
#     try:
#         spreadsheet = gc.open_by_key(sheet_id)
#         print("3. Successfully connected to Google Sheet document.")
        
#         users_sheet = spreadsheet.worksheet("Users")
#         print("4. Successfully found 'Users' tab.")
        
#         all_users = users_sheet.get_all_records()
#         print(f"5. Fetched {len(all_users)} rows from Users tab.")
        
#         if len(all_users) > 0:
#             print(f"6. Detected Column Headers: {list(all_users[0].keys())}")
        
#         clean_input_username = form_data.username.strip().lower()
        
#         user_record = None
#         for i, u in enumerate(all_users):
#             # Print exactly what we are comparing
#             sheet_uname_raw = u.get("Username", str(u.get("username", ""))) # Fallback just in case
#             sheet_uname_clean = str(sheet_uname_raw).strip().lower()
            
#             print(f"   -> Row {i+2}: Comparing '{sheet_uname_clean}' vs '{clean_input_username}'")
            
#             if sheet_uname_clean == clean_input_username:
#                 print("   ✅ USERNAME MATCH FOUND!")
#                 user_record = u
#                 break
        
#         if not user_record:
#             print("❌ ERROR: User not found in database loop.")
#             raise HTTPException(status_code=401, detail="User not found in database.")
            
#         clean_hash = str(user_record.get("Hashed_Password", "")).strip()
#         clean_input_password = form_data.password.strip()
        
#         print("7. Verifying password hash...")
#         if not verify_password(clean_input_password, clean_hash):
#             print("❌ ERROR: Password hash did not match.")
#             raise HTTPException(status_code=401, detail="Incorrect password.")
            
#         print("8. ✅ Password Verified! Issuing Token...")
#         clean_role = str(user_record.get("Role", "worker")).strip().lower()
#         actual_username = str(user_record.get("Username", "")).strip()
            
#         token_data = {"sub": actual_username, "role": clean_role, "sheet_id": sheet_id}
#         access_token = create_access_token(data=token_data)
        
#         print("="*40 + "\n")
#         return {
#             "access_token": access_token, 
#             "token_type": "bearer", 
#             "role": clean_role,
#             "username": actual_username
#         }
        
#     except gspread.exceptions.WorksheetNotFound:
#         print("❌ ERROR: Could not find a tab named exactly 'Users'.")
#         raise HTTPException(status_code=404, detail="Users sheet not found. Please check tab name.")
#     except gspread.exceptions.SpreadsheetNotFound:
#         print("❌ ERROR: Could not access the spreadsheet. Is the ID correct and shared with the bot?")
#         raise HTTPException(status_code=404, detail="Spreadsheet not found or bot lacks access.")
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         print(f"❌ FATAL ERROR: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")
# # -----------------------------------------------------------------
# # 5. PROTECTED ENDPOINTS
# # -----------------------------------------------------------------
# @app.get("/api/get-spec/{part_number}")
# def get_spec(part_number: str, sheet_id: str, current_user: dict = Depends(get_current_user)):
#     try:
#         spreadsheet = gc.open_by_key(sheet_id)
#         specs_sheet = spreadsheet.worksheet("Master_Specs")

#         raw = specs_sheet.get_all_values()
#         rows = raw[1:]

#         for row in rows:
#             if len(row) < 4:
#                 continue

#             sheet_code = clean(row[3])
#             incoming_code = clean(part_number)

#             if sheet_code == incoming_code:
#                 raw_params = []
#                 for idx in [5, 8, 11, 14]:
#                     if idx < len(row):
#                         val = row[idx].strip()
#                         if val and val != "-":
#                             raw_params.append(val)

#                 return {
#                     "found": True,
#                     "part_number": sheet_code,
#                     "part_name": row[2].strip(),
#                     "group": row[1].strip(),
#                     "parameters": raw_params
#                 }

#         raise HTTPException(status_code=404, detail="Part Code not found in Master Specs!")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.post("/api/log-inspection")
# def log_inspection(request: InspectionLogRequest, current_user: dict = Depends(get_current_user)):
#     # Verify the user is logging to the sheet they authenticated against
#     if request.sheet_id != current_user["sheet_id"]:
#         raise HTTPException(status_code=403, detail="Token does not match target sheet ID.")

#     try:
#         spreadsheet = gc.open_by_key(request.sheet_id)
#         log_sheet = spreadsheet.worksheet("Inspection_Logs")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to access sheet: {str(e)}")

#     # --- STAGE GATEKEEPER ---
# # ... (Keep the Stage Gatekeeper code above this) ...

#     # --- AI CATEGORIZATION ---
#     ai_category = "N/A"
#     ai_report = "N/A"

#     if request.status == "RED" and GEMINI_KEY:
#         measurements_str = ", ".join([f"{k}: {v}" for k, v in request.measured_values.items()])
#         prompt = f"""
#         You are a factory Quality Assurance assistant.
#         Part '{request.part_name}' was inspected at '{request.current_stage}'.
#         Situation: The part has been REJECTED (hard fail).
#         Parameter ratings: {measurements_str}
#         Worker remark: '{request.worker_remark or "None provided"}'

#         1. Categorize the issue in 1-3 words.
#         2. Write a short formal English report (1 sentence max) for management.

#         Format EXACTLY like this:
#         [CATEGORY] | [REPORT]
#         """
#         # PASTE THE BLOCK HERE:
#         try:
#             response = model.generate_content(prompt)
#             raw_text = response.text.replace("```", "").strip() # Strip markdown wrappers
#             parts = raw_text.split("|")
#             if len(parts) >= 2:
#                 ai_category = parts[0].strip()
#                 ai_report = parts[1].strip()
#             else:
#                 ai_report = raw_text
#         except Exception as e:
#             ai_report = f"AI Error: {str(e)}"

#     # --- SAVE TO GOOGLE SHEETS ---
#     try:
#         timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         formatted_measurements = " | ".join([f"{k}: {v}" for k, v in request.measured_values.items()])

#         row_data = [
#             timestamp,
#             request.part_number,
#             request.part_name,
#             request.current_stage,
#             formatted_measurements,
#             request.status,
#             request.worker_remark or "None",
#             ai_category,
#             ai_report,
#             current_user["username"] # Log who made the entry
#         ]

#         log_sheet.append_row(row_data)
#         return {"message": f"Successfully logged {request.current_stage} for {request.part_number} by {current_user['username']}!"}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to write to Google Sheets: {str(e)}")

# # -----------------------------------------------------------------
# # 6. ADMIN DASHBOARD ENDPOINTS
# # -----------------------------------------------------------------
# @app.get("/api/admin/dashboard-stats")
# def get_dashboard_stats(current_user: dict = Depends(require_admin)):
#     try:
#         spreadsheet = gc.open_by_key(current_user["sheet_id"])
#         log_sheet = spreadsheet.worksheet("Inspection_Logs")
#         all_logs = log_sheet.get_all_records()
        
#         total_inspections = len(all_logs)
#         failed_inspections = sum(1 for log in all_logs if str(log.get("Status")).strip().upper() in ["RED", "YELLOW"])
#         yield_rate = ((total_inspections - failed_inspections) / total_inspections * 100) if total_inspections > 0 else 100
        
#         # --- NEW PYTHON ANALYTICS ---
        
#         # 1. Today's Inspections
#         today_str = datetime.now().strftime("%Y-%m-%d")
#         today_total = sum(1 for log in all_logs if str(log.get("Timestamp", "")).startswith(today_str))
        
#         # 2. Top Defect Category
#         defect_counts = {}
#         stage_failures = {"Stage 1": 0, "Stage 2": 0, "Stage 3": 0}
        
#         for log in all_logs:
#             status = str(log.get("Status")).strip().upper()
#             if status in ["RED", "YELLOW"]:
#                 # Count AI Categories
#                 cat = str(log.get("AI Category", "N/A")).strip()
#                 if cat and cat != "N/A" and "AI Error" not in cat:
#                     defect_counts[cat] = defect_counts.get(cat, 0) + 1
                
#                 # Count Failures by Stage
#                 stage = str(log.get("Stage", str(log.get("current_stage", "")))).strip()
#                 if stage in stage_failures:
#                     stage_failures[stage] += 1
#                 else:
#                     stage_failures[stage] = 1 # Catch-all for misspellings

#         top_defect = "None"
#         if defect_counts:
#             # Find the category with the highest count
#             top_defect = max(defect_counts, key=defect_counts.get)
            
#         return {
#             "total_inspections": total_inspections,
#             "failed_inspections": failed_inspections,
#             "yield_rate": round(yield_rate, 2),
#             "today_total": today_total,
#             "top_defect": top_defect,
#             "stage_failures": stage_failures,
#             "logs": all_logs[-50:] # Last 50 rows
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime, timedelta, timezone
import gspread
import os
import jwt
import bcrypt
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
# 1. SECURITY CONFIGURATION
# -----------------------------------------------------------------
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        sheet_id: str = payload.get("sheet_id")
        if username is None or role is None:
            raise credentials_exception
        return {"username": username, "role": role, "sheet_id": sheet_id}
    except jwt.PyJWTError:
        raise credentials_exception

def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Admin privileges required.")
    return current_user

# -----------------------------------------------------------------
# 2. INITIALIZE GOOGLE SHEETS & AI
# -----------------------------------------------------------------
try:
    gc = gspread.service_account(filename='google_credentials.json')
    print("Connected to Google Service Account successfully!")
except Exception as e:
    print(f"Failed to connect to Google Service Account: {e}")

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
    sheet_id: str
    part_number: str
    part_name: str
    current_stage: str
    measured_values: Dict[str, str]
    status: str
    worker_remark: Optional[str] = None
    supplier: Optional[str] = None
    invoice_number: Optional[str] = None
    lot_quantity: Optional[str] = None
    checking_frequency: Optional[str] = None

class AIChatRequest(BaseModel):
    part_name: str
    current_stage: str
    measured_values: Dict[str, str]
    worker_message: str

def clean(s: str) -> str:
    return ''.join(str(s).split())

@app.get("/ping")
def ping_server():
    return {"message": "Python API is Live and Secure!"}

# -----------------------------------------------------------------
# 4. AUTHENTICATION ENDPOINT
# -----------------------------------------------------------------
@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), sheet_id: str = ""):
    print("\n" + "="*40)
    print("AUTHENTICATION DIAGNOSTIC STARTED")
    print(f"1. Target Sheet ID: '{sheet_id}'")
    print(f"2. Input Username: '{form_data.username}'")

    if not sheet_id:
        raise HTTPException(status_code=400, detail="sheet_id query parameter is required")

    try:
        spreadsheet = gc.open_by_key(sheet_id)
        users_sheet = spreadsheet.worksheet("Users")
        all_users = users_sheet.get_all_records()

        clean_input_username = form_data.username.strip().lower()
        user_record = None
        for i, u in enumerate(all_users):
            sheet_uname_raw = u.get("Username", str(u.get("username", "")))
            sheet_uname_clean = str(sheet_uname_raw).strip().lower()
            if sheet_uname_clean == clean_input_username:
                user_record = u
                break

        if not user_record:
            raise HTTPException(status_code=401, detail="User not found in database.")

        clean_hash = str(user_record.get("Hashed_Password", "")).strip()
        if not verify_password(form_data.password.strip(), clean_hash):
            raise HTTPException(status_code=401, detail="Incorrect password.")

        clean_role = str(user_record.get("Role", "worker")).strip().lower()
        actual_username = str(user_record.get("Username", "")).strip()
        token_data = {"sub": actual_username, "role": clean_role, "sheet_id": sheet_id}
        access_token = create_access_token(data=token_data)

        return {"access_token": access_token, "token_type": "bearer", "role": clean_role, "username": actual_username}

    except gspread.exceptions.WorksheetNotFound:
        raise HTTPException(status_code=404, detail="Users sheet not found. Please check tab name.")
    except gspread.exceptions.SpreadsheetNotFound:
        raise HTTPException(status_code=404, detail="Spreadsheet not found or bot lacks access.")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# -----------------------------------------------------------------
# 5. PROTECTED ENDPOINTS
# -----------------------------------------------------------------
@app.get("/api/get-spec/{part_number}")
def get_spec(part_number: str, sheet_id: str, current_user: dict = Depends(get_current_user)):
    try:
        spreadsheet = gc.open_by_key(sheet_id)
        specs_sheet = spreadsheet.worksheet("Master_Specs")
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/suppliers")
def get_suppliers(sheet_id: str, current_user: dict = Depends(get_current_user)):
    try:
        spreadsheet = gc.open_by_key(sheet_id)
        suppliers_sheet = spreadsheet.worksheet("Suppliers")
        all_rows = suppliers_sheet.get_all_values()

        supplier_col_index = 3  # Column D
        suppliers = [
            row[supplier_col_index].strip()
            for row in all_rows[1:]
            if len(row) > supplier_col_index and row[supplier_col_index].strip()
        ]
        return {"suppliers": suppliers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai-chat")
def ai_chat(request: AIChatRequest, current_user: dict = Depends(get_current_user)):
    if not GEMINI_KEY:
        raise HTTPException(status_code=503, detail="AI not configured.")
    measurements_str = ", ".join([f"{k}: {v}" for k, v in request.measured_values.items()])
    prompt = f"""
    You are a factory QA supervisor assistant.
    Part: '{request.part_name}', Stage: '{request.current_stage}'
    Parameter ratings: {measurements_str}
    Worker's question: '{request.worker_message}'

    Give a short, practical answer (2-3 sentences max) to help the worker decide.
    """
    try:
        response = model.generate_content(prompt)
        return {"reply": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")


@app.post("/api/log-inspection")
def log_inspection(request: InspectionLogRequest, current_user: dict = Depends(get_current_user)):
    if request.sheet_id != current_user["sheet_id"]:
        raise HTTPException(status_code=403, detail="Token does not match target sheet ID.")

    try:
        spreadsheet = gc.open_by_key(request.sheet_id)
        log_sheet = spreadsheet.worksheet("Inspection_Logs")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to access sheet: {str(e)}")

    # --- AI CATEGORIZATION (RED only) ---
    ai_category = "N/A"
    ai_report = "N/A"

    if request.status == "RED" and GEMINI_KEY:
        measurements_str = ", ".join([f"{k}: {v}" for k, v in request.measured_values.items()])
        prompt = f"""
        You are a factory Quality Assurance assistant.
        Part '{request.part_name}' was inspected at '{request.current_stage}'.
        Situation: The part has been REJECTED (hard fail).
        Parameter ratings: {measurements_str}
        Worker remark: '{request.worker_remark or "None provided"}'

        1. Categorize the issue in 1-3 words.
        2. Write a short formal English report (1 sentence max) for management.

        Format EXACTLY like this:
        [CATEGORY] | [REPORT]
        """
        try:
            response = model.generate_content(prompt)
            raw_text = response.text.replace("```", "").strip()
            parts = raw_text.split("|")
            if len(parts) >= 2:
                ai_category = parts[0].strip()
                ai_report = parts[1].strip()
            else:
                ai_report = raw_text
        except Exception as e:
            ai_report = f"AI Error: {str(e)}"

    # --- SAVE TO GOOGLE SHEETS ---
    # Column order: Timestamp | Part Name | Stage | Supplier | Invoice_Number | Lot_Quantity | Checking_Frequency | Measurements | Status | Worker Remark | AI Category | Logged By | AI Formal Report
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_measurements = " | ".join([f"{k}: {v}" for k, v in request.measured_values.items()])

        row_data = [
            timestamp,
            request.part_name,
            request.current_stage,
            request.supplier or "N/A",
            request.invoice_number or "N/A",
            request.lot_quantity or "N/A",
            request.checking_frequency or "N/A",
            formatted_measurements,
            request.status,
            request.worker_remark or "None",
            ai_category,
            current_user["username"],
            ai_report,
        ]

        log_sheet.append_row(row_data)
        return {"message": f"Successfully logged {request.current_stage} for {request.part_name} by {current_user['username']}!"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write to Google Sheets: {str(e)}")

# -----------------------------------------------------------------
# 6. ADMIN DASHBOARD ENDPOINTS
# -----------------------------------------------------------------
@app.get("/api/admin/dashboard-stats")
def get_dashboard_stats(current_user: dict = Depends(require_admin)):
    try:
        spreadsheet = gc.open_by_key(current_user["sheet_id"])
        log_sheet = spreadsheet.worksheet("Inspection_Logs")
        all_logs = log_sheet.get_all_records()

        total_inspections = len(all_logs)
        failed_inspections = sum(1 for log in all_logs if str(log.get("Status")).strip().upper() in ["RED", "YELLOW"])
        yield_rate = ((total_inspections - failed_inspections) / total_inspections * 100) if total_inspections > 0 else 100

        today_str = datetime.now().strftime("%Y-%m-%d")
        today_total = sum(1 for log in all_logs if str(log.get("Timestamp", "")).startswith(today_str))

        defect_counts = {}
        stage_failures = {"Stage 1": 0, "Stage 2": 0, "Stage 3": 0}

        for log in all_logs:
            status = str(log.get("Status")).strip().upper()
            if status in ["RED", "YELLOW"]:
                cat = str(log.get("AI Category", "N/A")).strip()
                if cat and cat != "N/A" and "AI Error" not in cat:
                    defect_counts[cat] = defect_counts.get(cat, 0) + 1
                stage = str(log.get("Stage", "")).strip()
                if stage in stage_failures:
                    stage_failures[stage] += 1
                else:
                    stage_failures[stage] = 1

        top_defect = "None"
        if defect_counts:
            top_defect = max(defect_counts, key=defect_counts.get)

        return {
            "total_inspections": total_inspections,
            "failed_inspections": failed_inspections,
            "yield_rate": round(yield_rate, 2),
            "today_total": today_total,
            "top_defect": top_defect,
            "stage_failures": stage_failures,
            "logs": all_logs[-50:]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))