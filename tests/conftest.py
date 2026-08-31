from unittest.mock import MagicMock
import numpy as np
import pytest


@pytest.fixture(autouse=True)
def mock_sentence_transformer(monkeypatch):
    """Bypass heavy sentence-transformer loading during tests."""

    class FakeEmbedder:
        def get_embedding_dimension(self):
            return 384

        def get_sentence_embedding_dimension(self):
            return self.get_embedding_dimension()

        def encode(self, sentences, **kwargs):
            if isinstance(sentences, str):
                sentences = [sentences]
            return np.zeros((len(sentences), 384), dtype=np.float32)

    # Keep compatibility with semantic-memory implementations that no longer
    # expose this legacy symbol. The production code is not changed by this
    # test seam.
    monkeypatch.setattr(
        "core.memory.semantic_memory.SentenceTransformer",
        lambda model_name: FakeEmbedder(),
        raising=False,
    )
