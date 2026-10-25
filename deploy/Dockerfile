# AIPIR detector service image (lab mode: replays HAI telemetry)
FROM python:3.12-slim
RUN useradd --uid 10001 --create-home aipir
WORKDIR /app
COPY deploy/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY framework/ framework/
COPY models/ models/
ENV PYTHONPATH=/app/framework AIPIR_RECOVERY=dry-run
USER 10001
EXPOSE 9108
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:9108/healthz')"
ENTRYPOINT ["python", "-m", "aipir.service"]
CMD ["--model", "models/aipir_hai2103.joblib", "--replay", "/data/test2.csv.gz", "--speed", "60", "--port", "9108"]
