import os
import time
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="LAN Network Health API")

# Environment variables (Render)
MAKE_API_KEY = os.getenv("MAKE_API_KEY", "make_network_health")
STALE_SECONDS = int(os.getenv("STALE_SECONDS", "300"))  # 5 minutes

# In-memory storage
LATEST: Dict[str, Dict[str, Any]] = {}


# 🔐 API key authentication (Make-safe)
def require_key(x_api_key: str = Header(...)):
    if x_api_key != MAKE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ✅ MAKE-SAFE PAYLOAD (NO 422)
class HealthPayload(BaseModel):
    device_id: str = Field(..., min_length=1)

    cpu: Optional[float] = Field(default=None, ge=0, le=100)
    ram: Optional[float] = Field(default=None, ge=0, le=100)
    temperature: Optional[float] = None

    status: Optional[str] = "OK"
    health_score: Optional[int] = Field(default=None, ge=0, le=100)
    extra: Optional[Dict[str, Any]] = None


# ✅ REQUIRED FOR MAKE CONNECTION VALIDATION
@app.get("/")
def root(_: None = Depends(require_key)):
    return {"status": "API is running"}


@app.post("/device/report")
def report_health(payload: HealthPayload, _: None = Depends(require_key)):
    data = payload.model_dump(exclude_none=True)

    # Optional defaults (safe)
    data.setdefault("status", "UNKNOWN")

    LATEST[payload.device_id] = {
        "data": data,
        "ts": time.time()
    }

    return {"ok": True, "stored_for": payload.device_id}


@app.get("/device/health")
def get_health(device_id: str, _: None = Depends(require_key)):
    item = LATEST.get(device_id)
    if not item:
        raise HTTPException(status_code=404, detail="No data yet for this device_id")

    age = time.time() - float(item["ts"])
    if age > STALE_SECONDS:
        raise HTTPException(
            status_code=503,
            detail=f"Device data is stale ({int(age)}s old)",
        )

    return item["data"]


@app.get("/devices/health")
def all_health(_: None = Depends(require_key)):
    return {k: v["data"] for k, v in LATEST.items()}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Render uses $PORT
    uvicorn.run(app, host="0.0.0.0", port=port)
