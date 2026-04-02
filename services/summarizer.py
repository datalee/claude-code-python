"""Summarizer Service - Text Summarization"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Summary:
    content: str
    key_points: List[str]
    original_length: int
    summary_length: int
    compression_ratio: float


class SummarizerService:
    def __init__(self) -> None:
        self._history: List[Summary] = []

    def summarize(self, text: str, max_length: int = 500, style: str = "concise") -> Summary:
        original_length = len(text)
        sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        
        if style == "concise":
            summary_text = ". ".join(sentences[:3])
        elif style == "bullet_points":
            summary_text = "\n".join(f"- {s}" for s in sentences[:5])
        else:
            summary_text = ". ".join(sentences[:5])

        if len(summary_text) > max_length:
            summary_text = summary_text[:max_length-3] + "..."

        key_points = [s for s in sentences if any(k in s.lower() for k in ["important", "key", "must", "should"])]
        
        summary = Summary(
            content=summary_text, key_points=key_points[:5],
            original_length=original_length, summary_length=len(summary_text),
            compression_ratio=len(summary_text) / original_length if original_length > 0 else 1.0)
        self._history.append(summary)
        return summary

    def summarize_conversation(self, messages: List[Dict[str, str]], max_messages: int = 10) -> Summary:
        text_parts = []
        for msg in messages[-max_messages:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:200]
            text_parts.append(f"{role}: {content}")
        return self.summarize("\n".join(text_parts), max_length=300)


_summarizer: Optional[SummarizerService] = None


def get_summarizer() -> SummarizerService:
    global _summarizer
    if _summarizer is None:
        _summarizer = SummarizerService()
    return _summarizer


__all__ = ["Summary", "SummarizerService", "get_summarizer"]
