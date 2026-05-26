from __future__ import annotations
import re
from collections import Counter
from typing import Literal

STOP_WORDS: dict[str, set[str]] = {
    "uk": {"і","та","в","у","на","до","з","за","що","як","але","або","це","той",
           "про","не","при","по","від","для","він","вона","вони","його","їх","ми",
           "ви","все","ще","вже","тому","через","коли","де","хто","між","над"},
    "hu": {"és","a","az","is","de","nem","van","egy","hogy","mint","ezt","azt",
           "vagy","meg","már","még","csak","erre","arra","ezek","aki","ami"},
    "sk": {"a","i","v","na","do","zo","za","sa","je","nie","ale","ako","alebo",
           "pre","pri","po","od","ich","sú","ten","tá","to","tie","tí","som"},
    "ro": {"și","în","la","de","cu","pe","că","din","este","sunt","sau","dar",
           "nu","mai","se","ale","prin","pentru","după","între","care","cel"},
    "en": {"the","a","an","in","on","at","to","for","of","and","or","but","is",
           "was","are","were","be","has","have","with","from","by","as","that",
           "this","it","not","also","its","their","about","after","more","all"},
}


def extract_keywords(
    text: str,
    language: str = "en",
    top_n: int = 20,
) -> list[str]:
    """
    Витягує топ-N ключових токенів (уніграми + біграми).

    Алгоритм:
      1. Токенізація — слова ≥3 символів, без стоп-слів
      2. TF score — частота в тексті
      3. Власні назви (велика літера, не початок речення) → ×3
      4. Довгі слова (≥7 символів) → ×1.5
      5. Біграми з топ-30 токенів → score = середнє × 0.6
    """
    stops = STOP_WORDS.get(language, STOP_WORDS["en"])

    # Власні назви: велика літера не на початку речення
    proper: set[str] = set()
    for sent in re.split(r'[.!?]\s+', text):
        words = sent.split()
        for w in words[1:]:
            clean = re.sub(r'[^\wа-яёіїєґА-ЯЁІЇЄҐA-Za-z\u00C0-\u024F]', '', w)
            if clean and clean[0].isupper() and len(clean) >= 3:
                proper.add(clean.lower())

    tokens = re.findall(
        r'[a-zA-Zа-яёіїєґА-ЯЁІЇЄҐ\u00C0-\u024F]{3,}',
        text.lower(),
    )
    tokens = [t for t in tokens if t not in stops]

    if not tokens:
        return []

    freq = Counter(tokens)
    total = len(tokens)

    scored: dict[str, float] = {}
    for tok, cnt in freq.items():
        tf   = cnt / total
        mult = 3.0 if tok in proper else (1.5 if len(tok) >= 7 else 1.0)
        scored[tok] = tf * mult

    # Біграми
    top_set = set(list(scored.keys())[:30])
    for i in range(len(tokens) - 1):
        if tokens[i] in top_set and tokens[i + 1] in top_set:
            bg = f"{tokens[i]} {tokens[i + 1]}"
            scored[bg] = (scored[tokens[i]] + scored[tokens[i + 1]]) * 0.6

    return [k for k, _ in sorted(scored.items(), key=lambda x: -x[1])[:top_n]]