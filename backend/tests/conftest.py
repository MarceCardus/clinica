import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "testsecret")
os.environ.setdefault("MINIO_ENDPOINT", "minio:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "test")
os.environ.setdefault("MINIO_SECRET_KEY", "testsecret")
os.environ.setdefault("MINIO_BUCKET", "test-bucket")
os.environ.setdefault("MINIO_SECURE", "false")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_MINUTES", "1440")
os.environ.setdefault("MAX_DAILY_TOPUP", "10000")
os.environ.setdefault("MAX_DAILY_STAKE", "5000")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "Admin1234!")
os.environ.setdefault("SEED_COMPANY", "Empresa Demo")

from app.main import app  # noqa: E402
from app.db.session import SessionLocal, engine, get_db  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.seed.seed_data import get_or_create_admin, seed_tournament  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        get_or_create_admin(session)
        seed_tournament(session)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c
