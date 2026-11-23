import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

数据目录 = Path(os.environ.get("数据目录", Path(__file__).resolve().parent.parent / "data"))
夹具目录 = Path(os.environ.get("夹具目录", Path(__file__).resolve().parent.parent.parent / "fixtures"))
库路径 = 数据目录 / "播浪.db"

_写锁 = threading.RLock()


def 连接() -> sqlite3.Connection:
    数据目录.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(库路径, isolation_level=None, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA busy_timeout = 5000")
    return c


@contextmanager
def 写事务():
    """写事务：BEGIN IMMEDIATE + 进程内写锁，异常整批回滚。

    迟到修正的「改窗合计」「写撤回单」「落事件」必须都在本上下文内完成，
    任何一步失败都回滚，杜绝「撤回单已落、窗行未动」的半截状态。
    """
    with _写锁:
        conn = 连接()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()


@contextmanager
def 读事务():
    """读事务：拿一个一致快照，避免多次 SELECT 之间被并发写事务穿插。"""
    conn = 连接()
    try:
        conn.execute("BEGIN")
        yield conn
    finally:
        try:
            conn.commit()
        finally:
            conn.close()
