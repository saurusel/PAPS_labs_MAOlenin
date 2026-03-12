from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.sqlalchemy_repositories import (
    SqlAlchemyLedgerRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyPointsRepository,
    SqlAlchemyProductRepository,
)


class SqlAlchemyRepositoryFactory:
    def __init__(self, db: Session):
        self.db = db

    def products(self):
        return SqlAlchemyProductRepository(self.db)

    def orders(self):
        return SqlAlchemyOrderRepository(self.db)

    def points(self):
        return SqlAlchemyPointsRepository(self.db)

    def ledger(self):
        return SqlAlchemyLedgerRepository(self.db)
