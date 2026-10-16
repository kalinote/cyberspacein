FROM python:3.13-slim

ENV TZ=Asia/Shanghai
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
RUN python -c "from app.service.nanobot.utils.tokenizer import get_token_encoder; get_token_encoder()"

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
