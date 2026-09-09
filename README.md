# PRAVAHA AI / Asteria Corridor Command Center

A live traffic management dashboard and microscopic traffic simulation backend.

## Requirements
- **Python**: 3.9+ (Tested on 3.11)
- **Node.js**: v18+ 
- **SUMO (Simulation of Urban MObility)**: v1.27.1

**Important Note on SUMO**: SUMO cannot be installed solely via Python pip. You must install the SUMO binaries on your host system and ensure the `sumo` command is in your system `$PATH`. 
- macOS: `brew install sumo`
- Ubuntu: `sudo apt-get install sumo sumo-tools sumo-doc`

## Setup Instructions

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
npm install
```

## Running the Application

1. **Start the Backend Server (with active virtual environment)**:
```bash
cd backend
uvicorn app.main:app --reload
```
*Note: The backend will automatically spawn a background thread to run SUMO via TraCI on startup.*

2. **Start the Frontend Development Server**:
```bash
cd frontend
npm run dev
```

3. Open your browser to the URL provided by the Vite frontend server (typically http://localhost:5173).
