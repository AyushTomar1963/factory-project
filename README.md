# Factory IQC Inspection Portal

A full-stack Quality Assurance portal built for factory environments. This system allows workers to log part inspections, enforces stage-based workflow rules, and uses Google's Gemini AI to automatically generate formal management reports for defective parts.

## 🚀 Features
* **QR Code Scanning:** Quickly load part configurations using a camera or barcode scanner.
* **Smart Master Specs:** Automatically fetches tolerance parameters (Go/Tight/Loose) from a centralized Google Sheet.
* **Workflow Gatekeeper:** Prevents parts from moving to advanced assembly stages if they haven't passed previous stages.
* **AI Defect Reporting:** Uses Gemini 2.5 Flash to automatically categorize defects and write 1-sentence formal reports for management when a part fails.
* **Live Dashboarding:** Pushes all inspection logs directly to a Google Sheet in real-time.

## 🛠️ Tech Stack
* **Frontend:** React, Vite, TailwindCSS, Html5Qrcode
* **Backend:** Python, FastAPI, Uvicorn
* **Database/Storage:** Google Sheets API (`gspread`)
* **AI:** Google Generative AI (`gemini-2.5-flash`)

## ⚙️ Local Setup Instructions

### 1. Backend Setup (FastAPI)
1. Navigate to the `backend` folder:
   ```bash
   cd backend
   pip install -r requirements.txt
   GEMINI_API_KEY="your_gemini_key"
SPREADSHEET_ID="your_google_sheet_id"
Start the local server:

Bash
uvicorn main:app --reload
2. Frontend Setup (React)
Open a new terminal and navigate to the frontend folder:

Bash
cd frontend
Install the Node modules:

Bash
npm install
Start the Vite development server:

Bash
npm run dev
