from fastapi.testclient import TestClient
from sqlmodel import Session

from interactem.app import crud
from interactem.app.core.config import settings
from interactem.app.models import User, UserCreate, UserUpdate
from interactem.app.tests.utils.utils import random_lower_string, random_username


def user_authentication_headers(
    *, client: TestClient, username: str, password: str
) -> dict[str, str]:
    data = {"username": username, "password": password}

    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_random_user(db: Session) -> User:
    username = random_username()
    password = random_lower_string()
    user_in = UserCreate(username=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    return user


def authentication_token_from_username(
    *, client: TestClient, username: str, db: Session
) -> dict[str, str]:
    """
    Return a valid token for the user with given username.

    If the user doesn't exist it is created first.
    """
    password = random_lower_string()
    user = crud.get_user_by_username(session=db, username=username)
    if not user:
        user_in_create = UserCreate(username=username, password=password)
        user = crud.create_user(session=db, user_create=user_in_create)
    else:
        user_in_update = UserUpdate(password=password)
        if not user.id:
            raise Exception("User id not set")
        user = crud.update_user(session=db, db_user=user, user_in=user_in_update)

    return user_authentication_headers(client=client, username=username, password=password)
