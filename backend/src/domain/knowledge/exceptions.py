# domain/knowledge/exceptions.py
from src.domain.shared.exceptions import DomainException


class ArticleNotFound(DomainException):
    def __init__(self, article_id):
        super().__init__(f"Article not found: {article_id}")


class DuplicateArticle(DomainException):
    def __init__(self, url: str):
        super().__init__(f"Article already exists: {url}")


class ArticleExpiredException(DomainException):
    def __init__(self, article_id):
        super().__init__(f"Article is expired: {article_id}")


class InvalidArticleStatus(DomainException):
    """Спроба перевести статтю в невалідний стан."""
    def __init__(self, current: str, target: str):
        super().__init__(f"Cannot transition article from '{current}' to '{target}'")
