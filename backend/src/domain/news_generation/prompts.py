# domain/news_generation/prompts.py
"""
Prompts and constants for news generation.

Centralized in the domain layer — prompt engineering is part of the
domain logic (business rules regarding style, format, language).

Isolated from use_cases and infrastructure:
  use_case takes the prompt from here → passes it to ILLMClient (port).
"""
from __future__ import annotations

# ── Generation constants ──────────────────────────────────────────────────────

# Minimum length of a found chunk to be included in the context
MIN_TEXT_LENGTH: int = 150

# Similarity threshold for selecting relevant chunks
SIMILARITY_THRESHOLD: float = 0.85

# Number of top chunks for the context
TOP_K_RESULTS: int = 5

# ── Stylistic template (example for LLM) ──────────────────────────────────────

STYLE_TEMPLATE = """\
Style example:
  Headline: "Specific, concise, captures the essence of the event"
  Lead (1-2 sentences): The most important details — who, what, where, when, why.
  Body (3-5 paragraphs): details, quotes, context, consequences.
  Tone: neutral, informational, without sensationalism.
  Length: 300–600 words.
"""

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an experienced Ukrainian journalist and editor.
Your task is to write a new news article based on the provided context.

Strict requirements:
1. Write EXCLUSIVELY in Ukrainian.
2. Adhere strictly to the provided style template.
3. Use ONLY the information from the provided context — do not invent facts.
4. Response structure: the first line is the headline, followed by a new line, and then the text of the news.
5. Do not mention that you are an AI or that you used the provided context.
"""

# ── User prompt template ──────────────────────────────────────────────────────

USER_PROMPT_TEMPLATE = """\
{style_template}

=== CONTEXT (relevant news from the archive) ===
{context_block}

=== TASK ===
Based on the provided context, write a new news article about: {query}

Format requirements:
- First line: news headline
- Followed by a new line: news text (lead + body)
"""


def build_user_prompt(query: str, context_chunks: list[str]) -> str:
    """Assembles the final user prompt from context chunks."""
    context_block = "\n\n---\n\n".join(
        f"[Source {i + 1}]\n{chunk.strip()}"
        for i, chunk in enumerate(context_chunks)
    )
    return USER_PROMPT_TEMPLATE.format(
        style_template=STYLE_TEMPLATE,
        context_block=context_block,
        query=query,
    )