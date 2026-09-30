"""Pure-Python WordPiece tokenizer for uncased BERT/DistilBERT vocabularies.

Written to avoid native tokenizer wheels, which are a common install failure on
Windows ARM64. Mirrors BertTokenizer(do_lower_case=True): lowercase, strip
accents, split on whitespace and punctuation, greedy longest-match WordPiece.
tools/export_model.py checks token parity against the Hugging Face tokenizer.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path


def _is_punct(ch: str) -> bool:
    cp = ord(ch)
    if 33 <= cp <= 47 or 58 <= cp <= 64 or 91 <= cp <= 96 or 123 <= cp <= 126:
        return True
    return unicodedata.category(ch).startswith("P")


def _is_cjk(cp: int) -> bool:
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF or
            0x2A700 <= cp <= 0x2CEAF or 0xF900 <= cp <= 0xFAFF or 0x2F800 <= cp <= 0x2FA1F)


class WordPieceTokenizer:
    def __init__(self, vocab_path: str | Path, max_length: int = 128, lowercase: bool = True):
        with open(vocab_path, "r", encoding="utf-8") as f:
            self.vocab = {line.rstrip("\n"): i for i, line in enumerate(f)}
        self.max_length = max_length
        self.lowercase = lowercase
        self.unk, self.cls, self.sep, self.pad = (self.vocab[t] for t in ("[UNK]", "[CLS]", "[SEP]", "[PAD]"))

    def _basic(self, text: str) -> list[str]:
        text = "".join(" " if unicodedata.category(c) == "Zs" or c in "\t\n\r" else c
                       for c in text if ord(c) not in (0, 0xFFFD) and not unicodedata.category(c).startswith("C")
                       or c in "\t\n\r")
        text = "".join(f" {c} " if _is_cjk(ord(c)) else c for c in text)
        if self.lowercase:
            text = unicodedata.normalize("NFD", text.lower())
            text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        tokens: list[str] = []
        for word in text.split():
            cur = ""
            for ch in word:
                if _is_punct(ch):
                    if cur:
                        tokens.append(cur)
                        cur = ""
                    tokens.append(ch)
                else:
                    cur += ch
            if cur:
                tokens.append(cur)
        return tokens

    def _wordpiece(self, word: str) -> list[int]:
        if len(word) > 100:
            return [self.unk]
        ids, start = [], 0
        while start < len(word):
            end, found = len(word), None
            while start < end:
                piece = ("##" if start > 0 else "") + word[start:end]
                if piece in self.vocab:
                    found = self.vocab[piece]
                    break
                end -= 1
            if found is None:
                return [self.unk]
            ids.append(found)
            start = end
        return ids

    def encode(self, text: str) -> tuple[list[int], list[int]]:
        """Return (input_ids, attention_mask), padded/truncated to max_length."""
        ids: list[int] = []
        for w in self._basic(text):
            ids.extend(self._wordpiece(w))
        ids = [self.cls] + ids[: self.max_length - 2] + [self.sep]
        mask = [1] * len(ids)
        pad = self.max_length - len(ids)
        return ids + [self.pad] * pad, mask + [0] * pad
