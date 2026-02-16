from collections.abc import Sequence

from sqlalchemy import BinaryExpression, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.fraud.models import FraudCheckLog


class FraudCheckLogGateway:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_total_count(
        self, filters: list[BinaryExpression]
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(FraudCheckLog)
            .where(*filters)
        )
        result = await self.session.execute(stmt)
        return result.scalar()

    async def get_all(
        self,
        limit: int,
        offset: int,
        filters: list[BinaryExpression],
    ) -> Sequence[FraudCheckLog]:
        stmt = (
            select(FraudCheckLog)
            .filter(*filters)
            .order_by(FraudCheckLog.created_at.desc())
            .offset(offset=offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, log_id: int) -> FraudCheckLog | None:
        stmt = select(FraudCheckLog).where(FraudCheckLog.id == log_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, log: FraudCheckLog) -> FraudCheckLog:
        self.session.add(log)
        await self.session.flush()
        return log
