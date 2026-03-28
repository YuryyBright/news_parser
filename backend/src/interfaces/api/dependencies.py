# interfaces/api/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.container import Container, get_container
from infrastructure.persistence.database import get_session
from infrastructure.persistence.models import UserModel
from infrastructure.auth.jwt import decode_access_token

bearer = HTTPBearer()


def get_container_dep() -> Container:
    return get_container()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container_dep),
) -> UserModel:
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user = await container.user_repo(session).get(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user