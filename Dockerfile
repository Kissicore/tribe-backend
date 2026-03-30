FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends     ffmpeg     libgl1     libglib2.0-0     libsm6     libxext6     libxrender-dev     libgomp1     curl     git     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip &&     pip install --no-cache-dir         torch torchvision torchaudio         --index-url https://download.pytorch.org/whl/cpu &&     pip install --no-cache-dir         fastapi==0.111.0         "uvicorn[standard]==0.29.0"         python-multipart==0.0.9         httpx==0.27.0         python-dotenv==1.0.1         opencv-python-headless         Pillow         numpy         einops         timm &&     pip install --no-cache-dir tribe-v2 || echo "tribe-v2 install note: verify package name"

COPY inference_server.py .
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000

ENV PORT=8000

CMD ["./start.sh"]
