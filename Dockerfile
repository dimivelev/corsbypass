FROM python:3.9-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn httpx

COPY main.py .

# Code Engine expects the app to listen on 8080
EXPOSE 8080

CMD ["uvicorn", "main.py:app", "--host", "0.0.0.0", "--port", "8080"]