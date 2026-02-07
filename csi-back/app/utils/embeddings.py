def get_embeddings_client():
    url = (settings.EMBEDDING_MODEL_URL or "").rstrip("/")
    base_url = url[: -len("/embeddings")].rstrip("/") if url.endswith("/embeddings") else url
    if not base_url or not settings.EMBEDDING_MODEL_API_KEY:
        raise HTTPException(status_code=503, detail="嵌入服务未配置")
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.EMBEDDING_MODEL_API_KEY,
        openai_api_base=base_url,
    )