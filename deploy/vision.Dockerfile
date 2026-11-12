# Vision microservice, built from services/vision UNCHANGED. Demo mode needs only Flask;
# for real face/ID recognition install backend/requirements.txt and set DEMO_MODE=0 (see README).
FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements-demo.txt .
RUN pip install --no-cache-dir -r requirements-demo.txt
COPY backend ./backend
ENV DEMO_MODE=1 PORT=5000
EXPOSE 5000
CMD ["python", "backend/app.py"]
