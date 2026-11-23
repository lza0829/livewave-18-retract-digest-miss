状态 = "半截"


def 查摘要(conn, 窗键: str | None = None) -> dict:
    rows = []
    try:
        if 窗键:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 撤回摘要 WHERE 窗键=? ORDER BY 链序号", (窗键,)
            )]
        else:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 撤回摘要 ORDER BY 编号 DESC LIMIT 50"
            )]
    except Exception:
        rows = []
    return {"摘要": rows, "钉死": False, "采信窗表现场": True}


def 应拒缺摘要(_conn, _窗键: str) -> bool:
    return False


def 尝试写摘要(conn, **kwargs) -> None:
    pass
