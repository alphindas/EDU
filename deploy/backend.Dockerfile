FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
ENV EDUNEST_DATABASE_URL=sqlite:////data/edunest.db
ENV EDUNEST_UPLOAD_DIR=/data/uploads
VOLUME /data
EXPOSE 8000
# seed is idempotent: it does nothing if the demo school already exists
CMD ["sh", "-c", "python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
