"""Multilingual danger similarity, computed locally against the reference examples."""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from huggingface_hub import hf_hub_download
from onnxruntime import InferenceSession, SessionOptions
from tokenizers import Tokenizer

MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


class SentenceEncoder:
    def __init__(self):
        tokenizer_path = hf_hub_download(MODEL_ID, "tokenizer.json", revision=MODEL_REVISION)
        model_path = hf_hub_download(MODEL_ID, "onnx/model.onnx", revision=MODEL_REVISION)
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        self.tokenizer.enable_truncation(max_length=384)
        options = SessionOptions()
        options.intra_op_num_threads = 4
        self.session = InferenceSession(model_path, sess_options=options, providers=["CPUExecutionProvider"])
        self.input_names = {item.name for item in self.session.get_inputs()}

    def encode(self, texts: list[str]) -> np.ndarray:
        batch = self.tokenizer.encode_batch([f"query: {text}" for text in texts])
        ids = np.asarray([item.ids for item in batch], dtype=np.int64)
        mask = np.asarray([item.attention_mask for item in batch], dtype=np.int64)
        candidates = {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}
        hidden = self.session.run(None, {key: candidates[key] for key in self.input_names})[0]
        pooled = (hidden * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1, keepdims=True)
        return (pooled / np.linalg.norm(pooled, axis=1, keepdims=True)).astype(np.float32)


@dataclass(frozen=True)
class DangerMatch:
    score: float
    example_id: str


class DangerDetector:
    def __init__(self, encoder: SentenceEncoder, ids: list[str], vectors: np.ndarray):
        if vectors.ndim != 2 or not ids or vectors.shape[0] != len(ids):
            raise ValueError("Invalid danger reference index")
        self.encoder = encoder
        self.ids = ids
        self.vectors = vectors

    @classmethod
    def from_course_examples(cls, encoder: SentenceEncoder, path: Path):
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        if len(rows) != 40 or len({row["danger_example_id"] for row in rows}) != 40:
            raise ValueError("Expected 40 distinct course reference examples")
        return cls(encoder, [row["danger_example_id"] for row in rows], encoder.encode([row["example_text"] for row in rows]))

    def match(self, messages: list[str]) -> list[DangerMatch]:
        scores = np.clip(self.encoder.encode(messages) @ self.vectors.T, -1.0, 1.0)
        closest = np.argmax(scores, axis=1)
        return [DangerMatch(float(scores[row, index]), self.ids[index]) for row, index in enumerate(closest)]
