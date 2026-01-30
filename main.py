import os
import httpx
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IBM_TARGET_URL = os.getenv(
    "IBM_TARGET_URL", 
    "https://eu-de.ml.cloud.ibm.com/ml/v4/deployments/proceduri000002/ai_service_stream?version=2021-05-01"
)

@app.get("/")
async def health_check():
    # Code Engine needs this to verify the app is "Live"
    return {"status": "healthy"}

@app.post("/proxy")
async def proxy_streaming_request(request: Request):
    body = await request.json()
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }

    async def event_generator():
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", IBM_TARGET_URL, json=body, headers=headers) as response:
                if response.status_code != 200:
                    yield f"IBM Error {response.status_code}".encode()
                    return
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    # CRITICAL: Read the PORT environment variable assigned by IBM Code Engine
    # Default to 8080 if not found (for local testing)
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)