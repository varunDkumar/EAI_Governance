import threading

_model = None
_model_lock = threading.Lock()

# ONNX Runtime-based embedding model (via fastembed) rather than sentence-transformers,
# since PyTorch publishes no wheels for Intel macOS on Python 3.13 in this environment.
MODEL_NAME = "BAAI/bge-small-en-v1.5"


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from fastembed import TextEmbedding

                _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_model()
    return [vector.tolist() for vector in model.embed(texts)]
