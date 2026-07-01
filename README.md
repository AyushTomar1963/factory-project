# Factory IQC Inspection Portal

A full-stack Quality Assurance portal built for factory environments. Workers log part inspections, stage-based workflow rules are enforced, and Google's Gemini AI generates formal management reports for defective parts.

## Features

- QR code scanning for part configuration lookup
- Stage-based inspection workflow (Stage 1 → 2 → 3)
- PostgreSQL-backed product specs, users, and inspection logs
- AI defect categorization via Gemini
- Admin dashboard with yield metrics and inspection history

## Tech Stack

- **Frontend:** React, Vite, Tailwind CSS, shadcn/ui (Nova)
- **Backend:** Python, FastAPI, Uvicorn, SQLAlchemy
- **Database:** PostgreSQL

## Local Setup

### 1. PostgreSQL

Install PostgreSQL locally, then create the database and user:

```sql
CREATE USER factory WITH PASSWORD 'change-me';
CREATE DATABASE factory_qa OWNER factory;
```

### 2. Backend

```bash
cd backend
copy .env.example .env
pip install -r requirements.txt
python seed_test_data.py
uvicorn main:app --reload
```

API runs at `http://localhost:8000`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:5173` (Vite proxies `/api` to the backend).

### Test logins

| Role   | Username | Password   |
|--------|----------|------------|
| Admin  | admin    | admin123   |
| Worker | worker   | worker123  |
