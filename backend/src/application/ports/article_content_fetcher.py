from abc import ABC, abstractmethod

class IArticleContentFetcher(ABC):
    @abstractmethod
    async def fetch_full_text(self, url: str) -> str | None: ...