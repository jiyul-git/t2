FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY online_server/requirements.txt /app/online_server/requirements.txt
RUN pip install --no-cache-dir -r /app/online_server/requirements.txt

COPY online_server /app/online_server

EXPOSE 8000

CMD ["uvicorn", "online_server.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
