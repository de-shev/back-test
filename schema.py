from contextlib import asynccontextmanager
from functools import partial
from typing import Protocol, cast, Any

import strawberry
from databases import Database
from fastapi import FastAPI
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry.types import Info

from settings import Settings


class Context(BaseContext):
    db: Database

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db


@strawberry.type
class Author:
    name: str


@strawberry.type
class Book:
    title: str
    author: Author


class _BookRecord(Protocol):
    book_title: str
    author_name: str


class BookRepo:
    _select_query = ("select "
                     "b.title as book_title, "
                     "a.name as author_name "
                     "from books b inner join public.authors a on a.id = b.author_id")

    def __init__(self, db: Database) -> None:
        self.db = db

    @classmethod
    def _build_sql_query_and_values(cls, author_ids: list[int] | None, search: str | None, limit: int | None) -> tuple[
        str, dict[str, Any]]:
        query = cls._select_query
        values: dict[str, Any] = {}

        filters = []
        if author_ids not in (None, []):
            filters.append("a.id = ANY(:author_ids)")
            values["author_ids"] = author_ids

        if search != (None, ""):
            filters.append("b.title ILIKE '%' || :search || '%'")
            values["search"] = search

        if filters:
            query = query + " where " + " and ".join(filters)

        if limit is not None:
            query += " limit :limit"
            values["limit"] = limit

        return query, values

    @staticmethod
    def _map_record_to_book(record: _BookRecord) -> Book:
        author = Author(name=record.author_name)

        return Book(title=record.book_title, author=author)

    async def get_books(
            self, author_ids: list[int] | None, search: str | None, limit: int | None
    ) -> list[Book]:
        query, values = self._build_sql_query_and_values(
            author_ids=author_ids,
            search=search,
            limit=limit,
        )

        book_records = cast(
            list[_BookRecord],
            await self.db.fetch_all(
                query=query, values=values
            ))

        return [self._map_record_to_book(r) for r in book_records]


@strawberry.type
class Query:
    @strawberry.field
    async def books(
            self,
            info: Info[Context, None],
            author_ids: list[int] | None = None,
            search: str | None = None,
            limit: int | None = None,
    ) -> list[Book]:
        return await BookRepo(db=info.context.db).get_books(
            author_ids=author_ids, search=search, limit=limit
        )


CONN_TEMPLATE = "postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
settings = Settings()  # type: ignore
db = Database(
    CONN_TEMPLATE.format(
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        port=settings.DB_PORT,
        host=settings.DB_SERVER,
        name=settings.DB_NAME,
    ),
)


@asynccontextmanager
async def lifespan(
        app: FastAPI,
        db: Database,
):
    async with db:
        yield
    await db.disconnect()


schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(  # type: ignore
    schema,
    context_getter=partial(Context, db),
)

app = FastAPI(lifespan=partial(lifespan, db=db))
app.include_router(graphql_app, prefix="/graphql")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("schema:app", host="0.0.0.0", reload=True)
