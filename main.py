import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 1. Setup CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with your Salesforce domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Configuration - Loaded from environment variables in Code Engine
IBM_TARGET_URL = os.getenv(
    "IBM_TARGET_URL", 
    "https://eu-de.ml.cloud.ibm.com/ml/v4/deployments/proceduri000002/ai_service_stream?version=2021-05-01"
)

@app.post("/proxy")
async def proxy_streaming_request(request: Request):
    # Get the JSON body and Authorization header from Salesforce
    body = await request.json()
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    # Prepare headers for IBM
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }

    async def event_generator():
        # Use httpx for asynchronous streaming
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", IBM_TARGET_URL, json=body, headers=headers) as response:
                if response.status_code != 200:
                    error_detail = await response.aread()
                    yield f"IBM Error {response.status_code}: {error_detail.decode()}".encode()
                    return

                # Pass chunks directly as they arrive from IBM
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # Use port 8080 (default for Code Engine)
    uvicorn.run(app, host="0.0.0.0", port=8080)