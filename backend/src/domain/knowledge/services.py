# domain/knowledge/services.py
import re

from langdetect import detect, LangDetectException
from .entities import Article, Tag
from .value_objects import Language


class ArticleClassificationService:
    """Чиста доменна логіка класифікації — без зовнішніх HTTP-запитів."""

    def detect_language(self, text: str) -> Language:
        try:
            code = detect(text[:500])  # достатньо перших 500 символів
            return Language(code) if code in Language._value2member_map_ else Language.UNKNOWN
        except LangDetectException:
            return Language.UNKNOWN

    def extract_auto_tags(self, article: Article) -> list[Tag]:
        """
        Спрощена версія — в production замінити на NER або LLM-класифікатор.
        Тут: keyword matching по заздалегідь визначеному словнику.
        """
        text = article.full_text.lower()
        TOPIC_KEYWORDS: dict[str, list[str]] = {
            "war_and_weapons": [
                # Українські основи (війна та зброя)
                "війн", "збро", "ракет", "атак", "удар", "зсу", "армія", "військ", 
                "оборон", "наступ", "дрон", "бпла", "артилері", "танк", "вибух", 
                "бомб", "окупант", "фронт", "піхот", "снаряд", "ппо", "авіац", 
                "обстріл", "солдат", "кулемет", "безпілот", "міномет", "бронетехнік",
                "балістич", "крилат", "шахед", "гелікоптер", "винищувач", "капітуляц",
                # Англійські слова
                "war", "attack", "missile", "strike", "military", "drone", "artillery",
                "tank", "weapon", "troops", "army", "defense", "offensive", "combat",
                "invasion", "bomb", "rocket", "uav", "radar", "frontline", "casualty",
                "air defense", "infantry", "ammunition"
            ],
            "politics": [
                # Українські основи
                "політ", "президент", "парламент", "уряд", "вибор", "депутат", 
                "міністр", "закон", "коаліці", "партія", "дипломат", "санкці", 
                "мерія", "сенат", "демократ", "референдум", "голосуван", "вето", 
                "законопроєкт", "опозиці", "конституці", "корупці", "судд",
                # Англійські слова
                "election", "president", "parliament", "sanctions", "government", 
                "voting", "diplomacy", "minister", "senate", "congress", "legislation", 
                "policy", "democracy", "vote", "coalition", "veto", "referendum",
                "diplomat", "campaign", "corruption"
            ],
            "economy": [
                # Українські основи
                "економік", "інфляці", "ввп", "ринок", "торгівл", "банк", "фінанс", 
                "інвестиц", "бюджет", "валют", "акці", "подат", "експорт", "імпорт", 
                "борг", "кредит", "прибут", "дефіцит", "бізнес", "компані", "грош",
                "економіч", "митни", "субсиді", "гран", "заробіт", "ціни",
                # Англійські слова
                "gdp", "inflation", "market", "trade", "bank", "finance", "investment", 
                "budget", "currency", "stock", "deficit", "tax", "revenue", "commerce", 
                "export", "import", "debt", "loan", "profit", "subsidy"
            ],
            "technology": [
                # Українські основи
                "технологі", "штучний інтелект", "стартап", "програмн", "кібер", 
                "айті", "it", "застосунок", "додаток", "алгоритм", "хмарн", "дан", 
                "інтернет", "робот", "крипто", "блокчейн", "цифров", "віртуальн", 
                "сервер", "мереж", "хакер", "смартфон", "інновац", "соцмереж",
                # Англійські слова
                "ai", "startup", "software", "cyber", "tech", "algorithm", "hardware", 
                "cloud", "data", "internet", "app", "robot", "crypto", "blockchain", 
                "digital", "virtual", "computing", "network", "server", "hacker", 
                "machine learning", "innovation"
            ],
        }
        tags = []
    
        for topic, keywords in TOPIC_KEYWORDS.items():
            # Формуємо регулярний вираз: \b означає межу слова
            # Це шукатиме слова, які ПОЧИНАЮТЬСЯ з нашого ключового слова/основи
            pattern = re.compile(r'\b(?:' + '|'.join(re.escape(kw) for kw in keywords) + r')')
            
            if pattern.search(text):
                tags.append(Tag(name=topic))
                
        return tags