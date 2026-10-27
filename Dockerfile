FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bookbridge ./bookbridge
EXPOSE 7860
CMD ["uvicorn","bookbridge.app:app","--host","0.0.0.0","--port","7860","--no-access-log","--no-proxy-headers"]
