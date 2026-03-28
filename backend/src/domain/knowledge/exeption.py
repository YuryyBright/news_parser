# domain/knowledge/exceptions.py
from domain.shared.exceptions import DomainException

class ArticleNotFound(DomainException): pass
class DuplicateArticle(DomainException):
    def __init__(self, url: str):
        super().__init__(f"Article already exists: {url}")