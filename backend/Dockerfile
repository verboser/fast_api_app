FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY solovei_nikita_fastapi.py .

CMD ["uvicorn", "solovei_nikita_fastapi:app", "--host", "0.0.0.0", "--port", "8000"]
