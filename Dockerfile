FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: jalankan demo rantai penuh sebagai bukti reprodusibilitas lokal.
# CATH mengganti CMD ini dengan service UI-nya (mis. uvicorn app:app) nanti.
CMD ["python", "demo.py"]
