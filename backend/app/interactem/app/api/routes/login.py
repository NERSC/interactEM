import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from interactem.app import crud
from interactem.app.api.deps import (
    CurrentUser,
    SessionDep,
    verify_external_token,
)
from interactem.app.core import security
from interactem.app.core.config import settings
from interactem.app.models import (
    ExternalTokenPayload,
    Token,
    UserCreate,
    UserPublic,
)
from interactem.core.logger import get_logger

logger = get_logger()

router = APIRouter()


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = crud.authenticate(
        session=session, username=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        nats_jwt=settings.NATS_JWT,
    )

@router.post("/login/external-token")
async def login_with_external_token(
    session: SessionDep,
    external_user: Annotated[ExternalTokenPayload, Depends(verify_external_token)],
) -> Token:
    """
    Login with an external token (e.g., distiller)
    """
    logger.info("Received login request from external user")
    username = f"{external_user.username}_external"

    user = crud.get_user_by_username(session=session, username=username)

    if not user:
        logger.info("Creating external user in db...")
        # password doesn't matter
        random_password = secrets.token_urlsafe(16)[:32]

        user_create = UserCreate(
            username=username,
            password=random_password,
            is_superuser=False,
            is_external=True,
        )

        try:
            user = crud.create_user(session=session, user_create=user_create)
        except Exception:
            raise HTTPException(
                status_code=400, detail="Could not create user in second server"
            )
        logger.info("External user created in db.")

    logger.info(f"External user `{external_user.username}` logged in.")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    now = datetime.now(timezone.utc)
    exp_datetime = datetime.fromtimestamp(external_user.exp, tz=timezone.utc)
    access_token_expires = exp_datetime - now

    logger.info(
        f"Token will expire at: {exp_datetime.strftime('%Y-%m-%d %I:%M:%S %p %Z')}"
    )
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        nats_jwt=settings.NATS_JWT,
    )


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


