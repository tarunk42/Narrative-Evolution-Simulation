from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import os
from pathlib import Path

app = FastAPI(title="EvoSim Dashboard")

# Mount static files if needed
# app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

DASHBOARD_DATA_FILE = Path(__file__).parent / "dashboard_data.json"

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Load data from file, or use defaults
    data = {
        "time_str": "12:00",
        "date_str": "2025-10-07",
        "city_metrics": ["Tiles: 1344", "Residential: 40%", "Commercial: 20%", "Industrial: 15%", "Parks: 10%", "Roads: 15%"],
        "population_metrics": ["Total Citizens: 10", "Employed: 8", "Unemployed: 2", "Active: 6"],
        "citizens": [
            {"name": "Maya Patel", "status": "Working", "location": "Office"},
            {"name": "Arjun Patel", "status": "Commuting", "location": "Road"},
        ],
        "events": ["Citizen Maya Patel started work", "New building constructed"]
    }

    if DASHBOARD_DATA_FILE.exists():
        try:
            with open(DASHBOARD_DATA_FILE, 'r') as f:
                data = json.load(f)
        except:
            pass  # Use defaults

    return templates.TemplateResponse("dashboard.html", {"request": request, **data})

@app.get("/api/data")
async def get_data():
    data = {
        "time_str": "12:00",
        "date_str": "2025-10-07",
        "city_metrics": ["Tiles: 1344"],
        "population_metrics": ["Total Citizens: 10"],
        "citizens": [],
        "events": []
    }
    if DASHBOARD_DATA_FILE.exists():
        try:
            with open(DASHBOARD_DATA_FILE, 'r') as f:
                data = json.load(f)
        except:
            pass
    return data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)