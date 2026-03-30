from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent
from src.domain.knowledge.services import ArticleClassificationService

class KeywordScoringService(IScoringService):
    """
    Рахує score як частку тематичних категорій що знайдені в тексті.
    0 категорій → 0.0, всі 4 → 1.0.
    Замінити на embedding-based scoring коли буде готово.
    """
    _MAX_TOPICS = 4  # war_and_weapons, politics, economy, technology

    def __init__(self) -> None:
        self._classifier = ArticleClassificationService()

    async def score(self, content: ParsedContent) -> float:
        from src.domain.knowledge.entities import Article
        from src.domain.knowledge.value_objects import ArticleStatus, Language

        # Тимчасово будуємо мінімальний Article щоб передати в extract_auto_tags
        tmp = Article(
            title=content.title,
            body=content.body,
            url=content.url,
            language=Language.UNKNOWN,
            status=ArticleStatus.PENDING,
        )
        tags = self._classifier.extract_auto_tags(tmp)
        return min(len(tags) / self._MAX_TOPICS, 1.0)