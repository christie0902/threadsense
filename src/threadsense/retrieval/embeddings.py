"""Local sentence-transformers encoder; offline unless a setup download is explicitly allowed."""
from threadsense.retrieval.config import EMBEDDING


class SentenceEncoder:
    """Encodes queries and documents identically (normalized, no prefixes)."""

    def __init__(self, config=EMBEDDING, *, allow_download=False):
        from sentence_transformers import SentenceTransformer
        from transformers.utils import logging
        logging.set_verbosity_error()  # Token-count calls on long texts are intentional.
        self.config = dict(config)
        self.allow_download = allow_download
        self.model = SentenceTransformer(config['model'], revision=config['revision'], device=config['device'],
                                         local_files_only=not allow_download)
        dimension = getattr(self.model, 'get_embedding_dimension', None) or self.model.get_sentence_embedding_dimension
        self.dimension = dimension()
        self.max_tokens = self.model.max_seq_length

    def count(self, text):
        """Model tokens including [CLS]/[SEP]; compared with max_seq_length to detect overflow."""
        return len(self.model.tokenizer(text, add_special_tokens=True, truncation=False)['input_ids'])

    def encode(self, texts):
        vectors = self.model.encode(list(texts), batch_size=32, normalize_embeddings=self.config['normalize_embeddings'],
                                    convert_to_numpy=True, show_progress_bar=False)
        return [list(map(float, row)) for row in vectors]

    def identity(self):
        return {**self.config, 'dimension': self.dimension, 'max_tokens': self.max_tokens}
