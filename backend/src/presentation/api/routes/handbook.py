# src/api/routers/handbook.py
"""
FastAPI router — Handbook API.

Mount in your main app:
    from src.api.routers.handbook import router as handbook_router
    app.include_router(handbook_router, prefix="/handbook", tags=["handbook"])

All write operations accept X-Changed-By header (username of editor).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.container import get_container

async def get_db_session():
    """
    Залежність FastAPI, яка бере сесію з нашого Singleton-контейнера
    та гарантує правильний lifecycle транзакції (commit/rollback).
    """
    container = get_container()
    async with container.db_session() as session:
        yield session
        
from src.infrastructure.persistence.repositories.handbook_repo import (
    CountryRepository,
    OrgUnitRepository,
    PersonRepository,
    NewsLinkRepository,
    HandbookSearchRepository,
)
from src.presentation.api.schemas.handbook_schemas import (
    CountryCreate, CountryUpdate, CountryOut, CountryDetail, PaginatedCountries,
    OrgUnitCreate, OrgUnitUpdate, OrgUnitOut,
    PersonCreate, PersonUpdate, PersonOut,
    NewsLinkCreate, NewsLinkOut,
    SearchResponse, SearchResult,
)

router = APIRouter()


def _editor(x_changed_by: str = Header(default="anonymous")) -> str:
    return x_changed_by


# ══════════════════════════════════════════════════════════════════════════════
# Countries
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/countries", response_model=PaginatedCountries)
async def list_countries(
    q: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CountryRepository(session)
    offset = (page - 1) * page_size
    items, total = await repo.list(q=q, is_active=is_active, limit=page_size, offset=offset)
    pages = (total + page_size - 1) // page_size
    return PaginatedCountries(
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


@router.post("/countries", response_model=CountryOut, status_code=201)
async def create_country(
    body: CountryCreate,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CountryRepository(session)
    existing = await repo.get_by_code(body.code)
    if existing:
        raise HTTPException(409, f"Country with code '{body.code}' already exists")
    data = body.model_dump()
    m = await repo.create(data, editor)
    await session.commit()
    return m


@router.get("/countries/{country_id}", response_model=CountryDetail)
async def get_country(
    country_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = CountryRepository(session)
    m = await repo.get_detail(country_id)
    if not m:
        raise HTTPException(404, "Country not found")
    return m


@router.patch("/countries/{country_id}", response_model=CountryOut)
async def update_country(
    country_id: str,
    body: CountryUpdate,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CountryRepository(session)
    data = body.model_dump(exclude_none=True)
    m = await repo.update(country_id, data, editor)
    if not m:
        raise HTTPException(404, "Country not found")
    await session.commit()
    return m


@router.delete("/countries/{country_id}", status_code=204)
async def delete_country(
    country_id: str,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CountryRepository(session)
    ok = await repo.delete(country_id, editor)
    if not ok:
        raise HTTPException(404, "Country not found")
    await session.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Org Units
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/countries/{country_id}/org-units", response_model=list[OrgUnitOut])
async def get_org_tree(
    country_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return flat list of all org units; tree structure built on frontend."""
    repo = OrgUnitRepository(session)
    items = await repo.get_tree(country_id)
    return items


@router.post("/org-units", response_model=OrgUnitOut, status_code=201)
async def create_org_unit(
    body: OrgUnitCreate,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = OrgUnitRepository(session)
    data = body.model_dump()
    m = await repo.create(data, editor)
    
    # 1. Flush to push changes to the DB and get the ID (keeps transaction open)
    await session.commit() 
    
    # 2. Re-fetch to load relationships (children, persons, etc.)
    return await repo.get(m.id)

@router.get("/org-units/{unit_id}", response_model=OrgUnitOut)
async def get_org_unit(
    unit_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = OrgUnitRepository(session)
    m = await repo.get(unit_id)
    if not m:
        raise HTTPException(404, "OrgUnit not found")
    return m


@router.patch("/org-units/{unit_id}", response_model=OrgUnitOut)
async def update_org_unit(
    unit_id: str,
    body: OrgUnitUpdate,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = OrgUnitRepository(session)
    data = body.model_dump(exclude_none=True)
    m = await repo.update(unit_id, data, editor)
    if not m:
        raise HTTPException(404, "OrgUnit not found")
        
    # Flush instead of commit
    await session.commit()  
    
    return await repo.get(unit_id)


@router.post("/org-units/{unit_id}/move", response_model=OrgUnitOut)
async def move_org_unit(
    unit_id: str,
    new_parent_id: str | None = Query(None),
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = OrgUnitRepository(session)
    m = await repo.move(unit_id, new_parent_id, editor)
    if not m:
        raise HTTPException(404, "OrgUnit not found")
        
    # Flush instead of commit
    await session.commit()
    
    return await repo.get(unit_id)


@router.delete("/org-units/{unit_id}", status_code=204)
async def delete_org_unit(
    unit_id: str,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = OrgUnitRepository(session)
    ok = await repo.delete(unit_id, editor)
    if not ok:
        raise HTTPException(404, "OrgUnit not found")
    await session.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Persons
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/countries/{country_id}/persons", response_model=list[PersonOut])
async def list_persons(
    country_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = PersonRepository(session)
    return await repo.list_by_country(country_id)


@router.post("/persons", response_model=PersonOut, status_code=201)
async def create_person(
    body: PersonCreate,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = PersonRepository(session)
    data = body.model_dump()
    m = await repo.create(data, editor)
    await session.commit()
    return m


@router.get("/persons/{person_id}", response_model=PersonOut)
async def get_person(
    person_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = PersonRepository(session)
    m = await repo.get(person_id)
    if not m:
        raise HTTPException(404, "Person not found")
    return m


@router.patch("/persons/{person_id}", response_model=PersonOut)
async def update_person(
    person_id: str,
    body: PersonUpdate,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = PersonRepository(session)
    data = body.model_dump(exclude_none=True)
    m = await repo.update(person_id, data, editor)
    if not m:
        raise HTTPException(404, "Person not found")
    await session.commit()
    return m


@router.delete("/persons/{person_id}", status_code=204)
async def delete_person(
    person_id: str,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = PersonRepository(session)
    ok = await repo.delete(person_id, editor)
    if not ok:
        raise HTTPException(404, "Person not found")
    await session.commit()

# ✅ Додати в handbook.py
@router.get("/news-links/generated-news/{generated_news_id}", response_model=list[NewsLinkOut])
async def get_links_for_generated_news(
    generated_news_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = NewsLinkRepository(session)
    return await repo.list_for_generated_news(generated_news_id)
# ══════════════════════════════════════════════════════════════════════════════
# News Links
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/news-links", response_model=NewsLinkOut, status_code=201)
async def create_news_link(
    body: NewsLinkCreate,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = NewsLinkRepository(session)
    data = body.model_dump()
    data["pinned_by"] = editor
    m = await repo.create(data)
    await session.commit()
    return m


@router.get("/news-links/article/{article_id}", response_model=list[NewsLinkOut])
async def get_links_for_article(
    article_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = NewsLinkRepository(session)
    return await repo.list_for_article(article_id)


@router.get("/news-links/{entity_type}/{entity_id}", response_model=list[NewsLinkOut])
async def get_links_for_entity(
    entity_type: str,
    entity_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = NewsLinkRepository(session)
    return await repo.list_for_entity(entity_type, entity_id)


@router.delete("/news-links/{link_id}", status_code=204)
async def delete_news_link(
    link_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = NewsLinkRepository(session)
    ok = await repo.delete(link_id)
    if not ok:
        raise HTTPException(404, "NewsLink not found")
    await session.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Search
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/search", response_model=SearchResponse)
async def search_handbook(
    q: str = Query(min_length=2),
    limit: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
):
    repo = HandbookSearchRepository(session)
    items = await repo.search(q, limit=limit)
    return SearchResponse(
        query=q,
        total=len(items),
        items=[SearchResult(**i) for i in items],
    )