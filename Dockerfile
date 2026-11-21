FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Dependencies first: this layer is cached as long as requirements.txt does not change.
COPY requirements.txt .
RUN pip install --retries 10 --timeout 120 -r requirements.txt

COPY pyproject.toml README.md ./
COPY src ./src
COPY sql ./sql
COPY sample_data ./sample_data
COPY dashboard ./dashboard
COPY .streamlit ./.streamlit
COPY tests ./tests
COPY docker-entrypoint.sh ./

# /app/data and /app/reports are created here, owned by the non-root user, so that
# named volumes mounted on them inherit write permissions.
RUN useradd --create-home app \
    && mkdir -p /app/data /app/reports \
    && chown -R app /app \
    && chmod +x docker-entrypoint.sh
USER app

EXPOSE 8501
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["pipeline"]
