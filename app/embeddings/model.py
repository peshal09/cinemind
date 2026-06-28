"""Sentence-embedding model and the text we embed for each movie.

We use sentence-transformers `all-MiniLM-L6-v2`: small, fast, 384-dim, and good
for short semantic-similarity text. The heavy import (torch / transformers) is
deferred into get_model() so that merely importing this module (e.g. for the
EMBEDDING_DIM constant) stays cheap and doesn't slow app startup.

Embeddings are L2-normalized, so cosine distance and inner product agree.
"""

from __future__ import annotations

# gte-small: a retrieval-tuned 384-dim model. Same dimension as the older
# all-MiniLM-L6-v2 (so no DB schema change), but markedly better at surfacing the
# right movie from a short thematic query (self-retrieval hit-rate@10 jumped from
# ~77% to ~97% on our eval). No query/passage instruction prefix needed.
MODEL_NAME = "thenlper/gte-small"
EMBEDDING_DIM = 384  # gte-small output size

_model = None


def get_model():
    """Lazily load and cache the SentenceTransformer (downloads on first use)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # heavy, import on demand

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def build_movie_text(
    title: str,
    genres: str | None,
    overview: str | None = None,
    keywords: list[str] | None = None,
    cast: list[str] | None = None,
) -> str:
    """Compose the natural-language text we embed for a movie.

    title + genres + overview + keywords + cast. overview/keywords/cast come from
    TMDB enrichment; when absent (e.g. pre-enrichment) they're simply skipped.
    Including cast lets actor questions ("movies starring X") retrieve the right films.
    """
    parts = [title or ""]
    if genres and genres != "(no genres listed)":
        parts.append("Genres: " + genres.replace("|", ", "))
    if overview:
        parts.append(overview)
    if keywords:
        parts.append("Keywords: " + ", ".join(keywords))
    if cast:
        parts.append("Cast: " + ", ".join(cast))
    return ". ".join(p for p in parts if p)


def embed_texts(texts: list[str], batch_size: int = 64):
    """Return an (n, 384) numpy array of unit-normalized embeddings."""
    model = get_model()
    return model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
