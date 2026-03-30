from __future__ import annotations

import asyncio
from typing import Iterable, List
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.risk import SensitiveWord, SensitiveWordAuditLog


class SensitiveWordsService:
    def __init__(self):
        self._cache: List[SensitiveWord] = []
        self._lock = asyncio.Lock()

    async def list_words(self, db, *, active_only: bool = False) -> List[SensitiveWord]:
        query = select(SensitiveWord).order_by(SensitiveWord.priority.asc(), SensitiveWord.id.asc())
        if active_only:
            query = query.where(SensitiveWord.is_active == True)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create_word(self, db, data) -> SensitiveWord:
        word = SensitiveWord(**data.model_dump())
        db.add(word)
        await db.flush()
        await db.commit()
        await self.invalidate_cache()
        return word

    async def update_word(self, db, word: SensitiveWord, data) -> SensitiveWord:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(word, field, value)
        word.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()
        await self.invalidate_cache()
        return word

    async def delete_word(self, db, word: SensitiveWord):
        await db.delete(word)
        await db.commit()
        await self.invalidate_cache()

    async def get_word(self, db, word_id: int):
        result = await db.execute(select(SensitiveWord).where(SensitiveWord.id == word_id))
        return result.scalar_one_or_none()

    async def invalidate_cache(self):
        async with self._lock:
            self._cache = []

    async def _get_cache(self, db) -> List[SensitiveWord]:
        async with self._lock:
            if not self._cache:
                self._cache = await self.list_words(db, active_only=True)
            return list(self._cache)

    async def find_matches(self, db, payload: dict) -> List[SensitiveWord]:
        text = self.extract_text(payload)
        if not text:
            return []

        lowered = text.lower()
        matches = []
        for word in await self._get_cache(db):
            if word.is_active and word.term.lower() in lowered:
                matches.append(word)
        return matches

    async def record_audit(self, db, *, path: str, user_id: int | None, client_ip: str, matched_word_ids: Iterable[int]):
        log = SensitiveWordAuditLog(
            path=path,
            user_id=user_id,
            client_ip=client_ip,
            matched_word_ids=list(matched_word_ids),
        )
        db.add(log)
        await db.flush()
        await db.commit()

    def extract_text(self, payload: dict) -> str:
        texts: List[str] = []
        for message in payload.get("messages", []) or []:
            content = message.get("content")
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        texts.append(item["text"])

        prompt = payload.get("prompt")
        if isinstance(prompt, str):
            texts.append(prompt)
        elif isinstance(prompt, list):
            texts.extend(str(item) for item in prompt)
        return "\n".join(texts)


_service = SensitiveWordsService()


def get_sensitive_words_service() -> SensitiveWordsService:
    return _service
