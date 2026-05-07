#!/usr/bin/env python3
# scripts/rag_cli.py
"""
CLI інструменти для RAG-пайплайну.

Команди:
  ingest   <file_or_dir>  — інгестувати .docx файл або директорію (рекурсивно)
  verify   <query>        — перевірити якість пошуку
  generate <query>        — згенерувати новину

Використання:
  python scripts/rag_cli.py ingest ./news_docs/
  python scripts/rag_cli.py ingest ./news_docs/article.docx
  python scripts/rag_cli.py verify "Зеленський виступив на саміті"
  python scripts/rag_cli.py generate "Ситуація на фронті"
  python scripts/rag_cli.py verify "запит" --top 15 --lang uk
  python scripts/rag_cli.py ingest ./docs/ --dry-run   # показати файли без інгестації

Потребує налаштованого .env (ті самі змінні що і основний застосунок).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Додаємо корінь проекту в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.WARNING,           # CLI — тільки попередження і помилки
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# RAG модулі — INFO щоб бачити прогрес
logging.getLogger("rag_cli").setLevel(logging.INFO)
logging.getLogger("application.use_cases").setLevel(logging.INFO)

logger = logging.getLogger("rag_cli")
from src.application.use_cases.generate_news import GenerateNewsUseCase

# ── Shared: ініціалізація Container ──────────────────────────────────────────

async def _get_container():
    """
    Ініціалізує головний Container (той самий що FastAPI використовує).
    Замість окремого build_rag_container() — всі залежності вже в Container.
    """
    from src.config.container import init_container
    container = init_container()
    await container.init_async()
    return container


# ── Команда: ingest ───────────────────────────────────────────────────────────

def _collect_docx(path: Path) -> list[Path]:
    """
    Рекурсивно збирає всі .docx файли.
    Ігнорує тимчасові файли Word (~$*.docx).
    """
    if path.is_file():
        if path.suffix.lower() == ".docx" and not path.name.startswith("~$"):
            return [path]
        else:
            logger.warning("Not a .docx file: %s", path)
            return []

    # Директорія — rglob рекурсивно по всіх вкладених папках
    files = sorted(
        p for p in path.rglob("*.docx")
        if not p.name.startswith("~$")
    )
    return files


async def cmd_ingest(path_str: str, dry_run: bool = False, workers: int = 1) -> None:
    target = Path(path_str).resolve()

    if not target.exists():
        print(f"❌ Path does not exist: {target}")
        sys.exit(1)

    files = _collect_docx(target)

    if not files:
        print(f"⚠️  No .docx files found in: {target}")
        return

    # ── Dry-run: тільки показати знайдені файли ───────────────────────────────
    if dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN — {len(files)} file(s) found in: {target}")
        print(f"{'='*60}")
        for i, f in enumerate(files, 1):
            # Показуємо відносний шлях для читабельності
            try:
                rel = f.relative_to(target if target.is_dir() else target.parent)
            except ValueError:
                rel = f
            print(f"  [{i:>3}] {rel}")
        print(f"\nRun without --dry-run to ingest.")
        return

    # ── Реальна інгестація ────────────────────────────────────────────────────
    container = await _get_container()

    if target.is_file():
        # Один файл
        logger.info("Ingesting single file: %s", target)
        result = await container.ingest_single_uc.execute(str(target))
        print(f"\n{'='*60}")
        if result.status == "ok":
            print(f"✅ {result.file_path}")
            print(f"   Chunks: {result.saved_chunks} saved, {result.skipped_chunks} skipped")
        else:
            print(f"❌ {result.file_path}")
            print(f"   Error: {result.error}")
        return

    # Директорія — батч з прогрес-репортом
    logger.info("Ingesting %d files from: %s", len(files), target)

    print(f"\n{'='*60}")
    print(f"Batch ingest: {len(files)} file(s) from {target}")
    print(f"{'='*60}")

    total_chunks = 0
    ok_files: list[str] = []
    failed: list[tuple[str, str]] = []

    for i, filepath in enumerate(files, 1):
        try:
            rel = filepath.relative_to(target)
        except ValueError:
            rel = filepath

        print(f"  [{i:>{len(str(len(files)))}}/{len(files)}] {rel} ...", end=" ", flush=True)

        result = await container.ingest_single_uc.execute(str(filepath))

        if result.status == "ok":
            print(f"✅  {result.saved_chunks} chunks")
            total_chunks += result.saved_chunks
            ok_files.append(str(rel))
        else:
            print(f"❌  {result.error}")
            failed.append((str(rel), result.error))

    # Підсумок
    print(f"\n{'='*60}")
    print(f"Done: {len(ok_files)}/{len(files)} files ok  ({len(failed)} failed)")
    print(f"Total chunks saved: {total_chunks}")

    if failed:
        print(f"\nFailed files:")
        for path_str, err in failed:
            print(f"  ❌ {path_str}: {err}")


# ── Команда: verify ───────────────────────────────────────────────────────────

async def cmd_verify(query: str, top: int = 10, lang: str | None = None) -> None:
    container = await _get_container()
    result = await container.verify_uc.execute(query=query, top_n=top, language_filter=lang)
    result.print_report()


# ── Команда: generate ─────────────────────────────────────────────────────────

async def cmd_generate(query: str, language: str = "uk") -> None:
    container = await _get_container()
    container.generate_uc._language = language

    async with container.db_session() as session:
        news_repo = container.generated_news_repo(session)
        uc = GenerateNewsUseCase(
            embedder=container._rag_embedder,
            chunk_repo=container._chunk_repo,
            llm_client=container._llm_client,
            news_repo=news_repo,
        )
        result = await uc.execute(query=query)
        news = result.news

    print(f"\n{'='*60}")
    print(f"Generation result: status={news.status.value}")
    print(f"Context: {result.context_chunks_used}/{result.context_chunks_found} chunks used")
    print(f"Avg context score: {news.context_score:.4f}")

    if news.title:
        print(f"\n📰 {news.title}")
        print(f"\n{news.body}")
    else:
        print(f"\n⚠️  {news.body}")

    if result.saved_path:
        print(f"\n💾 Saved: {result.saved_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ingest ./docs/                        # рекурсивна інгестація директорії
  %(prog)s ingest ./docs/article.docx            # один файл
  %(prog)s ingest ./docs/ --dry-run              # подивитись файли без інгестації
  %(prog)s verify "Зеленський виступив" --top 15 --lang uk
  %(prog)s generate "Ситуація на фронті"
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── ingest ────────────────────────────────────────────────────────────────
    p_ingest = sub.add_parser(
        "ingest",
        help="Ingest .docx file or directory (recursive)",
    )
    p_ingest.add_argument(
        "path",
        help="Path to a .docx file or directory (searched recursively)",
    )
    p_ingest.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="List found files without ingesting",
    )

    # ── verify ────────────────────────────────────────────────────────────────
    p_verify = sub.add_parser("verify", help="Verify vector search quality")
    p_verify.add_argument("query", help="Search query")
    p_verify.add_argument("--top", type=int, default=10, help="Number of results (default: 10)")
    p_verify.add_argument("--lang", type=str, default=None, help="Language filter, e.g. 'uk'")

    # ── generate ──────────────────────────────────────────────────────────────
    p_gen = sub.add_parser("generate", help="Generate news article via RAG")
    p_gen.add_argument("query", help="Topic / query for generation")
    p_gen.add_argument("--lang", type=str, default="uk", help="Output language (default: uk)")

    args = parser.parse_args()

    if args.command == "ingest":
        asyncio.run(cmd_ingest(args.path, dry_run=args.dry_run))
    elif args.command == "verify":
        asyncio.run(cmd_verify(args.query, top=args.top, lang=args.lang))
    elif args.command == "generate":
        asyncio.run(cmd_generate(args.query, language=args.lang))


if __name__ == "__main__":
    main()