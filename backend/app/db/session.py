"""数据持久化层（SQLite + SQLAlchemy 2.x）。

提供 engine / Session 依赖注入 / 建表入口。SQLite 适用于骨架演进，DB URL
可通过 AIOPS_DATABASE_URL 切换到 ":memory:" 或后续其它关系型数据库。
"""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def make_engine(database_url: str, **kwargs):
    """创建 engine。SQLite 追加合适的 connect_args；非 SQLite 由调用方接管。"""
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(database_url, connect_args=connect_args, **kwargs)


class Database:
    """封装 engine 与 Session 工厂，供 FastAPI 依赖注入。"""

    def __init__(self, database_url: str) -> None:
        self.engine = make_engine(database_url)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        """依据已注册模型建表（含新增模型）；生产演进使用 Alembic 迁移。"""
        Base.metadata.create_all(self.engine)

    def new_session(self) -> Session:
        """创建独立 Session（调用方负责 commit/close）。供 Agent 类自管理事务使用。"""
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """请求级 Session 上下文：提交/回滚自动处理。用法: with db.session_scope() as session:"""
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
