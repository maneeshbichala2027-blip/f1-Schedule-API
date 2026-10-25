FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api.py scrape_schedule.py session_times.py ./
ENV STATE_DIR=/data
RUN mkdir /data && useradd --uid 10001 --create-home app && chown app /data
USER app
EXPOSE 8000
CMD ["uvicorn", "api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
