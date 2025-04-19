from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pydantic import BaseModel
import asyncio
import random
import datetime
import os
from dotenv import load_dotenv
import uvicorn
import json

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://TuneTonicUser:nimda%40007@cluster0.r2ykx.mongodb.net/intrusion-detectionnew")
client = MongoClient(MONGODB_URI)
db = client.get_database()
logs_collection = db.logs

# WebSocket connections
active_connections = []

class LogEntry(BaseModel):
    type: str
    source_ip: str
    action_taken: str
    details: dict = {}

@app.get("/")
async def root():
    return {"message": "Intrusion Detection System API"}

@app.get("/api/logs")
async def get_logs():
    logs = list(logs_collection.find({}).sort("timestamp", -1).limit(100))
    # Convert ObjectId to string for JSON serialization
    for log in logs:
        log["_id"] = str(log["_id"])
        # Ensure timestamp is serializable
        if isinstance(log.get("timestamp"), datetime.datetime):
            log["timestamp"] = log["timestamp"].isoformat()
    return logs

@app.post("/api/logs")
async def create_log(log: LogEntry):
    log_dict = log.dict()
    log_dict["timestamp"] = datetime.datetime.utcnow()
    result = logs_collection.insert_one(log_dict)
    
    # Broadcast to all connected WebSocket clients
    log_dict["_id"] = str(result.inserted_id)
    log_dict["timestamp"] = log_dict["timestamp"].isoformat()
    await broadcast_log(log_dict)
    
    return {"id": str(result.inserted_id)}

@app.websocket("/api/logs/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def broadcast_log(log):
    for connection in active_connections:
        try:
            await connection.send_text(json.dumps(log))
        except:
            # Remove dead connections
            if connection in active_connections:
                active_connections.remove(connection)

# Intrusion detection simulation
async def simulate_intrusions():
    types = [
        "Suspicious Login Attempt",
        "Port Scan Detected",
        "Unauthorized Access Attempt",
        "Brute Force Attack",
        "SQL Injection Attempt",
        "XSS Attack Detected",
        "File Inclusion Attempt",
        "Command Injection Attempt",
    ]
    
    actions = ["Blocked", "Logged", "Allowed", "Quarantined"]
    
    while True:
        # Generate random IP
        source_ip = f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
        
        # Create log entry
        log_entry = LogEntry(
            type=random.choice(types),
            source_ip=source_ip,
            action_taken=random.choice(actions),
            details={"severity": random.choice(["Low", "Medium", "High", "Critical"])}
        )
        
        # Save to database and broadcast
        log_dict = log_entry.dict()
        log_dict["timestamp"] = datetime.datetime.utcnow()
        result = logs_collection.insert_one(log_dict)
        
        # Broadcast to WebSocket clients
        log_dict["_id"] = str(result.inserted_id)
        log_dict["timestamp"] = log_dict["timestamp"].isoformat()
        await broadcast_log(log_dict)
        
        # Wait random time between 5-30 seconds
        await asyncio.sleep(random.randint(5, 30))

@app.on_event("startup")
async def startup_event():
    # Start intrusion simulation in background
    asyncio.create_task(simulate_intrusions())

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)