FROM python:3.12-slim-bookworm
WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/api.py .
USER 10001:10001
EXPOSE 8080
CMD ["python", "-u", "api.py"]
