from dataclasses import dataclass

from .parsers import ExtractedUnit

CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150


@dataclass
class Chunk:
    text: str
    page_number: int | None
    slide_number: int | None


def chunk_units(units: list[ExtractedUnit]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for unit in units:
        words = unit.text.split()
        if not words:
            continue
        current: list[str] = []
        current_len = 0
        for word in words:
            current.append(word)
            current_len += len(word) + 1
            if current_len >= CHUNK_SIZE_CHARS:
                chunks.append(Chunk(text=" ".join(current), page_number=unit.page_number, slide_number=unit.slide_number))
                overlap_words = []
                overlap_len = 0
                for w in reversed(current):
                    overlap_len += len(w) + 1
                    overlap_words.insert(0, w)
                    if overlap_len >= CHUNK_OVERLAP_CHARS:
                        break
                current = overlap_words
                current_len = overlap_len
        if current:
            chunks.append(Chunk(text=" ".join(current), page_number=unit.page_number, slide_number=unit.slide_number))
    return chunks
