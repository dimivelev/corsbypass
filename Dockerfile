FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn httpx

COPY main.py .

# We still expose 8080 as a hint, but the app is now dynamic
EXPOSE 8080

CMD ["python", "main.py"]