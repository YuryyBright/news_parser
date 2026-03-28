# infrastructure/workers/handlers.py
"""
Handlers — тонкий шар між task queue і application use cases.
Єдиний файл який імпортує і application і infrastructure.
Це дозволено бо handlers — це "glue code" на рівні infrastructure.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


async def handle_fetch_source(source_id: str) -> dict:
    # Імпорт тут — lazy, не при старті модуля
    from infrastructure.config.container import get_container
    from application.ingestion.use_cases import TriggerFetchUseCase

    container = get_container()
    async with container.make_session() as session:
        uc = TriggerFetchUseCase(
            source_repo=container.source_repo(session),
            task_queue=container.task_queue,
        )
        return await uc.execute(source_id)


async def handle_process_article(raw_article_id: str) -> dict:
    from infrastructure.config.container import get_container
    from application.ingestion.use_cases import IngestArticleUseCase

    container = get_container()
    async with container.make_session() as session:
        uc = IngestArticleUseCase(
            article_repo=container.article_repo(session),
            criteria_repo=container.criteria_repo(session),
            embedding_service=container.embedding_service,
            chroma_store=container.chroma_store,
        )
        return await uc.execute(raw_article_id)


async def handle_generate_criteria(user_id: str, prompt: str) -> dict:
    from infrastructure.config.container import get_container
    from application.filtering.use_cases import GenerateCriteriaUseCase

    container = get_container()
    async with container.make_session() as session:
        uc = GenerateCriteriaUseCase(
            criteria_repo=container.criteria_repo(session),
            llm_service=container.llm_service,
            embedding_service=container.embedding_service,
            chroma_store=container.chroma_store,
        )
        return await uc.execute(user_id, prompt)