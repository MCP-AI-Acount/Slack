FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "common.slack_n8n_gateway"]
