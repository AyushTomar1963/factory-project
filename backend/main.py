from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import os, jwt, bcrypt
import google.generativeai as genai
from dotenv import load_dotenv

from database import get_db, engine
from models import Base, User, Supplier, Product, InspectionLog

load_dotenv()
Base.metadata.create_all(bind=engine)  # auto-creates tables on startup

app = FastAPI()

_cors_origins = os.getenv("CORS_ORIGINS", "*")
allow_origins = ["*"] if _cors_origins.strip() == "*" else [o.strip() for o in _cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth config ───────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-secret")
ALGORITHM  = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def create_access_token(data: dict, expires_minutes: int = 480) -> str:
    to_encode = {**data, "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role     = payload.get("role")
        if not username or not role:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "role": role}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

def require_admin(current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user

# ── Gemini AI ─────────────────────────────────────────────────────────────────
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash")

# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class InspectionLogRequest(BaseModel):
    part_number:        str
    part_name:          str
    current_stage:      str
    measured_values:    Dict[str, str]
    status:             str
    worker_remark:      Optional[str] = None
    supplier:           Optional[str] = None
    invoice_number:     Optional[str] = None
    lot_quantity:       Optional[str] = None
    checking_frequency: Optional[str] = None

class AIChatRequest(BaseModel):
    part_name:       str
    current_stage:   str
    measured_values: Dict[str, str]
    worker_message:  str

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/ping")
def ping(): return {"message": "API Live — PostgreSQL backend", "status": "ok"}

@app.get("/health")
def health(): return {"status": "ok"}

# LOGIN — no sheet_id anymore
@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.username == form_data.username.strip().lower(),
        User.is_active == True
    ).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer",
            "role": user.role, "username": user.username}

# GET SPEC — lookup by part_number in DB
@app.get("/api/get-spec/{part_number}")
def get_spec(part_number: str, db: Session = Depends(get_db),
             current_user=Depends(get_current_user)):
    product = db.query(Product).filter(
        Product.part_number == part_number.strip().upper(),
        Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Part not found")
    return {
        "found":       True,
        "part_number": product.part_number,
        "part_name":   product.part_name,
        "group":       product.group_name,
        "parameters":  product.parameters,
    }

# GET SUPPLIERS
@app.get("/api/suppliers")
def get_suppliers(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    suppliers = db.query(Supplier.supplier_name).all()
    return {"suppliers": [s[0] for s in suppliers]}

# AI CHAT
@app.post("/api/ai-chat")
def ai_chat(req: AIChatRequest, current_user=Depends(get_current_user)):
    if not GEMINI_KEY:
        raise HTTPException(status_code=503, detail="AI not configured")
    prompt = f"""You are a factory QA supervisor assistant.
Part: '{req.part_name}', Stage: '{req.current_stage}'
Parameter ratings: {', '.join(f'{k}: {v}' for k,v in req.measured_values.items())}
Worker's question: '{req.worker_message}'
Give a short, practical answer (2-3 sentences max)."""
    try:
        resp = gemini_model.generate_content(prompt)
        return {"reply": resp.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# LOG INSPECTION
@app.post("/api/log-inspection")
def log_inspection(req: InspectionLogRequest, db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    ai_category, ai_report = "N/A", "N/A"
    if req.status == "RED" and GEMINI_KEY:
        measurements_str = ", ".join(f"{k}: {v}" for k,v in req.measured_values.items())
        prompt = f"""Factory QA assistant. Part '{req.part_name}' REJECTED at '{req.current_stage}'.
Ratings: {measurements_str}. Remark: '{req.worker_remark or "None"}'.
1. Categorize issue in 1-3 words. 2. One-sentence formal report.
Format EXACTLY: [CATEGORY] | [REPORT]"""
        try:
            raw = gemini_model.generate_content(prompt).text.replace("```","").strip()
            parts = raw.split("|")
            if len(parts) >= 2:
                ai_category, ai_report = parts[0].strip(), parts[1].strip()
        except Exception as e:
            ai_report = f"AI Error: {e}"

    log = InspectionLog(
        part_name          = req.part_name,
        part_number        = req.part_number,
        stage              = req.current_stage,
        supplier           = req.supplier or "N/A",
        invoice_number     = req.invoice_number or "N/A",
        lot_quantity       = int(req.lot_quantity) if req.lot_quantity else None,
        checking_frequency = int(req.checking_frequency) if req.checking_frequency else None,
        measured_values    = req.measured_values,
        status             = req.status,
        worker_remark      = req.worker_remark or "None",
        ai_category        = ai_category,
        ai_report          = ai_report,
        logged_by          = current_user["username"],
    )
    db.add(log)
    db.commit()
    return {"message": f"Logged {req.current_stage} for {req.part_name} by {current_user['username']}"}

# ADMIN DASHBOARD
@app.get("/api/admin/dashboard-stats")
def dashboard_stats(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    from sqlalchemy import func as sqlfunc

    all_logs  = db.query(InspectionLog).all()
    total     = len(all_logs)
    failed    = sum(1 for l in all_logs if l.status in ("RED","YELLOW"))
    yield_pct = round((total - failed) / total * 100, 2) if total else 100

    today_str = datetime.now().date()
    today_total = sum(1 for l in all_logs if l.timestamp and l.timestamp.date() == today_str)

    defect_counts = {}
    stage_failures = {}
    for log in all_logs:
        if log.status in ("RED","YELLOW"):
            if log.ai_category and log.ai_category not in ("N/A",) and "AI Error" not in log.ai_category:
                defect_counts[log.ai_category] = defect_counts.get(log.ai_category, 0) + 1
            stage_failures[log.stage] = stage_failures.get(log.stage, 0) + 1

    top_defect = max(defect_counts, key=defect_counts.get) if defect_counts else "None"

    logs_serialized = [{
        "Timestamp":          str(l.timestamp),
        "Part Name":          l.part_name,
        "Stage":              l.stage,
        "Supplier":           l.supplier,
        "Invoice_Number":     l.invoice_number,
        "Lot_Quantity":       l.lot_quantity,
        "Checking_Frequency": l.checking_frequency,
        "Status":             l.status,
        "AI Category":        l.ai_category,
        "Logged By":          l.logged_by,
    } for l in all_logs[-50:]]

    return {
        "total_inspections": total,
        "failed_inspections": failed,
        "yield_rate": yield_pct,
        "today_total": today_total,
        "top_defect": top_defect,
        "stage_failures": stage_failures,
        "logs": logs_serialized,
    }

# ── Admin CRUD endpoints (new) ─────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "worker"

class ProductCreate(BaseModel):
    part_number: str
    part_name: str
    group_name: Optional[str] = None
    parameters: List[str]

class SupplierCreate(BaseModel):
    supplier_name: str
    contact_info: Optional[str] = None

@app.post("/api/admin/users")
def create_user(req: UserCreate, db: Session = Depends(get_db),
                current_user=Depends(require_admin)):
    username = req.username.strip().lower()
    if req.role not in ("admin", "worker"):
        raise HTTPException(status_code=400, detail="Role must be admin or worker")
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    user = User(username=username, hashed_password=hashed, role=req.role)
    db.add(user); db.commit()
    return {"message": f"User '{username}' created"}

@app.get("/api/admin/users")
def list_users(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    users = db.query(User).filter(User.is_active == True).order_by(User.username).all()
    return [{"username": u.username, "role": u.role} for u in users]

@app.post("/api/admin/products")
def create_product(req: ProductCreate, db: Session = Depends(get_db),
                   current_user=Depends(require_admin)):
    existing = db.query(Product).filter(
        Product.part_number == req.part_number.strip().upper()
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Part number already exists")
    if not req.parameters:
        raise HTTPException(status_code=400, detail="At least one parameter is required")
    product = Product(part_number=req.part_number.strip().upper(),
                      part_name=req.part_name, group_name=req.group_name,
                      parameters=req.parameters)
    db.add(product); db.commit()
    return {"message": f"Product '{req.part_number}' created"}

@app.get("/api/admin/products")
def list_products(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    products = db.query(Product).filter(Product.is_active == True).all()
    return [{"part_number": p.part_number, "part_name": p.part_name,
             "group": p.group_name, "parameters": p.parameters} for p in products]

class ProductUpdate(BaseModel):
    part_name: Optional[str] = None
    group_name: Optional[str] = None
    parameters: Optional[List[str]] = None

@app.put("/api/admin/products/{part_number}")
def update_product(part_number: str, req: ProductUpdate, db: Session = Depends(get_db),
                   current_user=Depends(require_admin)):
    product = db.query(Product).filter(
        Product.part_number == part_number.strip().upper(),
        Product.is_active == True,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Part not found")
    if req.part_name is not None:
        product.part_name = req.part_name
    if req.group_name is not None:
        product.group_name = req.group_name
    if req.parameters is not None:
        if not req.parameters:
            raise HTTPException(status_code=400, detail="At least one parameter is required")
        product.parameters = req.parameters
    db.commit()
    return {"message": f"Product '{part_number}' updated"}

@app.delete("/api/admin/products/{part_number}")
def deactivate_product(part_number: str, db: Session = Depends(get_db),
                       current_user=Depends(require_admin)):
    product = db.query(Product).filter(
        Product.part_number == part_number.strip().upper(),
        Product.is_active == True,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Part not found")
    product.is_active = False
    db.commit()
    return {"message": f"Product '{part_number}' deactivated"}

@app.post("/api/admin/suppliers")
def create_supplier(req: SupplierCreate, db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    existing = db.query(Supplier).filter(
        Supplier.supplier_name == req.supplier_name.strip()
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Supplier already exists")
    supplier = Supplier(supplier_name=req.supplier_name.strip(),
                        contact_info=req.contact_info)
    db.add(supplier); db.commit()
    return {"message": f"Supplier '{req.supplier_name}' created"}

@app.get("/api/admin/suppliers")
def list_suppliers_admin(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    suppliers = db.query(Supplier).order_by(Supplier.supplier_name).all()
    return [{"id": s.id, "supplier_name": s.supplier_name,
             "contact_info": s.contact_info} for s in suppliers]