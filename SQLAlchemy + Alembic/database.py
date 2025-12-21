from collections.abc import Sequence
from os import getenv

from sqlalchemy import Select, create_engine
from sqlalchemy.orm import Session


def get_database_url(
    scheme: str = "postgresql+psycopg",
    dbname: str = "alembic",
    default: str | None = None,
) -> str:
    DATABASE_URL = getenv("DATABASE_URL")
    if DATABASE_URL:
        return DATABASE_URL.replace("postgresql://", f"{scheme}://")

    DATABASE_HOSTNAME = getenv("DATABASE_HOSTNAME")
    DATABASE_USERNAME = getenv("DATABASE_USERNAME")
    DATABASE_PASSWORD = getenv("DATABASE_PASSWORD")
    if DATABASE_HOSTNAME and DATABASE_USERNAME and DATABASE_PASSWORD:
        return f"{scheme}://{DATABASE_USERNAME}:{DATABASE_PASSWORD}@{DATABASE_HOSTNAME}/{dbname}"

    return default or f"{scheme}://postgres@localhost/{dbname}"


engine = create_engine(get_database_url())


def fetch_all[T](stmt: Select[tuple[T]]) -> Sequence[T]:
    with Session(engine) as session:
        return session.scalars(stmt).all()


def fetch_first[T](stmt: Select[tuple[T]]) -> T | None:
    """
    取得した結果の最初の1件のみを返す
    0件の場合 None を返す
    """
    with Session(engine) as session:
        return session.scalars(stmt).first()


def fetch_one[T](stmt: Select[tuple[T]]) -> T:
    """
    取得した結果がちょうど1件のときのみ返す
    0件の場合はエラー (NoResultFound)
    2件以上の場合はエラー (MultipleResultsFound)
    """
    with Session(engine) as session:
        return session.scalars(stmt).one()


def fetch_one_or_none[T](stmt: Select[tuple[T]]) -> T | None:
    """
    取得した結果がちょうど1件のとき返す
    0件の場合は None を返す
    2件以上の場合はエラー (MultipleResultsFound)
    """
    with Session(engine) as session:
        return session.scalars(stmt).one_or_none()
