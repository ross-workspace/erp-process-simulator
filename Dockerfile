FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home appuser
COPY app.py ./
COPY dashboard ./dashboard
COPY app_pages ./app_pages
COPY data ./data
COPY .streamlit ./.streamlit
USER appuser
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
