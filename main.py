import os
import httpx
import uvicorn
import time
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

# --- CONFIGURATION ---
IBM_TARGET_URL = os.getenv(
    "IBM_TARGET_URL", 
    "https://eu-de.ml.cloud.ibm.com/ml/v4/deployments/proceduri000002/ai_service_stream?version=2021-05-01"
)
# Add your API Key here or in Environment Variables
IBM_API_KEY = os.getenv("IBM_API_KEY", "YOUR_ACTUAL_IBM_API_KEY_HERE")

# --- TOKEN MANAGEMENT ---
_cached_token = None
_token_expiry = 0

async def get_ibm_bearer_token():
    """
    Exchanges API Key for an IAM Bearer Token.
    Caches the token to avoid hitting the auth server on every request.
    """
    global _cached_token, _token_expiry
    
    # Return cached token if still valid (minus 60s buffer)
    if _cached_token and time.time() < (_token_expiry - 60):
        return _cached_token

    url = "https://iam.cloud.ibm.com/identity/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": IBM_API_KEY
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, data=data)
        if resp.status_code != 200:
            print(f"Auth Failed: {resp.text}")
            raise HTTPException(status_code=500, detail="Could not authenticate with IBM Cloud")
        
        json_resp = resp.json()
        _cached_token = json_resp["access_token"]
        # Set expiry (usually 1 hour)
        _token_expiry = time.time() + json_resp.get("expires_in", 3600)
        
        return _cached_token

@app.get("/")
async def health_check():
    return {"status": "healthy"}

@app.post("/proxy")
async def proxy_streaming_request(request: Request):
    body = await request.json()
    
    # 1. Get a fresh token (Middleware handles auth now!)
    try:
        token = await get_ibm_bearer_token()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth Error: {str(e)}")

    # 2. Prepare Headers for IBM
    ibm_headers = {
        "Authorization": f"Bearer {token}",  # Inject the generated token
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }

    async def event_generator():
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream("POST", IBM_TARGET_URL, json=body, headers=ibm_headers) as response:
                    
                    if response.status_code == 401:
                        yield b"Error: Unauthorized (Check API Key)\n"
                        return
                    
                    if response.status_code != 200:
                        yield f"Error: Upstream {response.status_code}".encode()
                        return

                    # 3. Stream and Filter Garbage
                    async for line in response.aiter_lines():
                        if line.startswith("id:") or line.startswith("event:"):
                            continue
                        if not line.strip():
                            continue
                        
                        # Yield clean text
                        yield line.encode() + b"\n"
            except Exception as e:
                yield f"Stream Connection Error: {str(e)}".encode()

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)