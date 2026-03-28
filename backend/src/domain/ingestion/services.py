# domain/ingestion/services.py
from .entities import RawArticle, Source, FetchJob
from .value_objects import ParsedContent
from .repositories import IRawArticleRepository
from .exceptions import SourceUnreachable


class IngestionDomainService:
    """
    Бізнес-правила інгестії — тут вирішується чи приймати статтю.
    Не знає про HTTP, Telegram, парсери — це infrastructure.
    """

    def create_raw_article(
        self,
        source: Source,
        content: ParsedContent,
    ) -> RawArticle:
        if not source.is_active:
            raise SourceUnreachable(f"Source {source.id} is disabled")

        article = RawArticle(source_id=source.id, content=content)
        article.mark_ingested()
        return article

    def should_refetch(self, job: FetchJob, schedule_seconds: int) -> bool:
        from datetime import datetime, timezone
        if job.last_run_at is None:
            return True
        elapsed = (datetime.now(timezone.utc) - job.last_run_at).total_seconds()
        return elapsed >= schedule_seconds