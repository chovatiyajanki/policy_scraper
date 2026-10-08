# 🚗 Vehicle Policy & Specs Scraper

Full-stack application to automatically scrape, extract, and store Indian vehicle details and insurance policy expiration dates by car registration number (e.g. `XX00XX0000`).

## 🛠️ Tech Stack

- **Frontend**: React 19 + Vite + Lucide Icons
- **Backend**: FastAPI (Python 3.14 / 3.10+) + Uvicorn + Playwright
- **Database**: PostgreSQL (via SQLAlchemy + Psycopg 3)
- **Environment Management**: `python-dotenv` & `.env`

---

## 📁 Project Structure

```text
insurance-scraper/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI Endpoints (/api/policies)
│   │   ├── models/          # SQLAlchemy Database Models (VehiclePolicy)
│   │   ├── schemas/         # Pydantic Request & Response Validation
│   │   ├── services/        # Playwright & Aggregator Scraper Engine
│   │   ├── database.py      # PostgreSQL Engine & Session Configuration
│   │   └── main.py          # FastAPI Application Entrypoint
│   ├── venv/                # Python Virtual Environment
│   ├── .env                 # Environment Variables (Database URL, Port)
│   ├── .env.example         # Template for environment configuration
│   └── requirements.txt     # Python Dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Interactive Search & Policy Card Dashboard
│   │   ├── App.css          # Styling matching exact reference screenshots
│   │   ├── index.css        # Typography & Design System
│   │   └── main.jsx         # React Root Entrypoint
│   ├── package.json         # React Dependencies
│   └── vite.config.js       # Vite Config & API Proxy
└── README.md
```

---

## ⚙️ Setup & Installation

### 1. Database Setup (PostgreSQL)

Ensure PostgreSQL is running locally on your machine and create the database:
```sql
CREATE DATABASE vehicle_policy;
```

### 2. Backend Setup (FastAPI)

1. Open a terminal in the `backend` directory:
   ```powershell
   cd backend
   ```

2. Activate virtual environment (or create a new one):
   ```powershell
   # Create virtual environment if needed
   python -m venv venv

   # Activate virtual environment
   .\venv\Scripts\Activate.ps1
   ```

3. Install all required dependencies from `requirements.txt`:
   ```powershell
   pip install -r requirements.txt
   ```

4. Configure environment variables in `backend/.env`:
   ```env
   DATABASE_URL=postgresql+psycopg://<username>:<password>@localhost:5432/vehicle_policy
   HOST=127.0.0.1
   PORT=8000
   JWT_SECRET_KEY=<a-strong-random-secret>
   ACCESS_TOKEN_EXPIRE_MINUTES=10080
   ```
   Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

5. Start the FastAPI backend server:
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```
   - API Docs will be available at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### 3. Frontend Setup (React + Vite)

1. Open a terminal in the `frontend` directory:
   ```powershell
   cd frontend
   ```

2. Install dependencies:
   ```powershell
   npm install
   ```

3. Start the development server:
   ```powershell
   npm run dev
   ```

4. Open your browser at [http://localhost:5173/](http://localhost:5173/).

---

## 🔍 Features

- **Car Number Lookup**: Enter an Indian vehicle registration plate (e.g. `XX00XX0000`).
- **Exact Field Extraction**:
  - **Vehicle Model & Make**: `MARUTI SWIFT VXI`
  - **Vehicle Type**: `Private` / `Commercial`
  - **Registration Date**: `19 January, 2021`
  - **Manufacturing Month**: `December-2020`
  - **Policy Expiry Date**: `14-Oct-2026` (with active / expiring countdown)
  - **RTO & Specs**: Owner Name, Surat RTO (GJ05), 1197 CC Engine, 5 Seater, Color.
- **PostgreSQL Persistence**: Saves all looked-up policies to the local database automatically.
- **Search History Table**: Search past records, delete unwanted ones, and **Export to CSV**.
