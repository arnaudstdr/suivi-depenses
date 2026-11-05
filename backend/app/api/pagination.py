from typing import Annotated

from fastapi import Query
from pydantic import BaseModel


class PageParams:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
