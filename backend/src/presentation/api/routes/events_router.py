# ══════════════════════════════════════════════════════════════════════════════
# FastAPI router
# Підключити в main.py:
#   from src.presentation.api.routers.handbook_events import router as events_router
#   app.include_router(events_router, prefix="/handbook", tags=["handbook-events"])
# ══════════════════════════════════════════════════════════════════════════════
 
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.persistence.repositories.handbook_events_repo import EventRepository
from src.config.container import get_container
 
from src.presentation.api.schemas.handbook_event_schemas import EventCreate, EventUpdate, EventOut
 
router = APIRouter()
 
 
async def get_db_session():
    container = get_container()
    async with container.db_session() as session:
        yield session
 
 
def _editor(x_changed_by: str = Header(default="anonymous")) -> str:
    return x_changed_by
 
 
# ── CRUD ──────────────────────────────────────────────────────────────────────
 
@router.post("/events", response_model=EventOut, status_code=201)
async def create_event(
    body: EventCreate,
    editor: str = Depends(_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    data = body.model_dump()
    m = await repo.create(data, created_by=editor)
    await session.commit()
    return m
 
 
@router.get("/events/{event_id}", response_model=EventOut)
async def get_event(
    event_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    m = await repo.get(event_id)
    if not m:
        raise HTTPException(404, "Event not found")
    return m
 
 
@router.patch("/events/{event_id}", response_model=EventOut)
async def update_event(
    event_id: str,
    body: EventUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    data = body.model_dump(exclude_none=True)
    m = await repo.update(event_id, data)
    if not m:
        raise HTTPException(404, "Event not found")
    await session.commit()
    return m
 
 
@router.delete("/events/{event_id}", status_code=204)
async def delete_event(
    event_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    ok = await repo.delete(event_id)
    if not ok:
        raise HTTPException(404, "Event not found")
    await session.commit()
 
 
# ── List by entity ─────────────────────────────────────────────────────────────
 
@router.get("/persons/{person_id}/events", response_model=list[EventOut])
async def list_person_events(
    person_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    return await repo.list_for_person(person_id)
 
 
@router.get("/org-units/{org_unit_id}/events", response_model=list[EventOut])
async def list_org_unit_events(
    org_unit_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    return await repo.list_for_org_unit(org_unit_id)
 
 
@router.get("/countries/{country_id}/events", response_model=list[EventOut])
async def list_country_events(
    country_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    return await repo.list_for_country(country_id)
 
 
@router.get("/articles/{article_id}/events", response_model=list[EventOut])
async def list_article_events(
    article_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Всі заходи, що були виявлені/прив'язані до конкретної статті."""
    repo = EventRepository(session)
    return await repo.list_for_article(article_id)

# ══════════════════════════════════════════════════════════════════════════════
# Events by entity
# ══════════════════════════════════════════════════════════════════════════════
 
@router.get("/persons/{person_id}/events", response_model=list[EventOut])
async def get_person_events(
    person_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    return await repo.list_for_person(person_id)
 
 
@router.get("/org-units/{org_unit_id}/events", response_model=list[EventOut])
async def get_org_unit_events(
    org_unit_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    return await repo.list_for_org_unit(org_unit_id)
 
 
@router.get("/countries/{country_id}/events", response_model=list[EventOut])
async def get_country_events(
    country_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    return await repo.list_for_country(country_id)
 
 
@router.get("/events/by-article/{article_id}", response_model=list[EventOut])
async def get_events_for_article(
    article_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    repo = EventRepository(session)
    return await repo.list_for_article(article_id)
