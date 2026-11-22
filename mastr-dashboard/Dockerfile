FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction

COPY app.py ./
COPY pages/ ./pages/
COPY utils/ ./utils/

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
