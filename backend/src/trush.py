import numpy as np
from uuid import uuid4
from domain.filtering.services import FilteringDomainService, SignalWeights
from domain.filtering.entities import FilterCriteria
from domain.filtering.value_objects import EmbeddingVector

# 1. Готуємо "Моки" (заглушки) даних
service = FilteringDomainService()

# Імітуємо вектор статті (наприклад, про космос)
# У реальному житті це число згенероване моделлю в infrastructure
mock_article_vector = np.array([0.1, 0.8, 0.1]) 
article_emb = EmbeddingVector(vector=mock_article_vector, model_version="v1")
article_text = "NASA успішно запустила новий телескоп для вивчення далеких зірок."

# 2. Налаштовуємо критерії користувача (що він шукає)
criteria = FilterCriteria(
    id=uuid4(),
    user_profile_id=uuid4(),
    phrases=["космічні дослідження", "технології"],
    # Мокаємо вектори для цих фраз (вони мають бути схожі на вектор статті)
    phrase_embeddings=np.array([
        [0.1, 0.75, 0.15], # схоже на космос
        [0.5, 0.1, 0.4]    # техніка
    ]),
    keywords=["NASA", "телескоп"],
    threshold=0.5,      # поріг проходження
    feedback_prior=0.5  # нейтральний фідбек
)

# 3. Запускаємо розрахунок
result = service.compute_relevance(
    article_embedding=article_emb,
    article_text=article_text,
    criteria=criteria
)

# 4. Дивимось результат
print(f"Фінальний скор: {result.score}")
print(f"Чи пройшла стаття: {'ТАК' if result.passed else 'НІ'}")
print(f"Деталі (Emb/KW/FB): {result.emb_score} / {result.kw_score} / {result.fb_score}")