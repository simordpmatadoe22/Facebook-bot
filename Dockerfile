FROM python:3.11-slim

# ffmpeg خاص لـ yt-dlp باش يدمج الفيديو والصوت إيلا جاو منفصلين
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app", "--timeout", "120"]
