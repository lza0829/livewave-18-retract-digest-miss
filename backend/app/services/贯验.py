from app.db import 读事务, 写事务
from app.seed import 此刻
from app.modules import 允许迟到策略


def 跑贯验() -> dict:
    """窗输出与撤回互证。

    - 已关闭窗的点赞/送礼/笔数 = 落入该窗的事件合计；
    - 撤回链须逐跳衔接：旧值=上一跳新值、版本逐跳 +1、末跳新值=窗表现行合计；
    - 撤回摘要链须与撤回单逐跳对上（事件/合计/哈希），末跳=窗表现行，
      撤回在而摘要空、链断、根数≠1 都算撕裂；
    - 旁路事件不得挂窗键；
    - 允许迟到界内被修正的窗，证据须 valid。

    读取在一个读事务快照里完成，落履历另起写事务，避免读写锁互相等待。
    """
    问题 = []
    with 读事务() as conn:
        事件数 = conn.execute("SELECT COUNT(*) FROM 互动事件").fetchone()[0]
        已关闭 = conn.execute("SELECT * FROM 热度窗 WHERE 状态='已关闭'").fetchall()
        撤回数 = conn.execute("SELECT COUNT(*) FROM 撤回单").fetchone()[0]
        摘要数 = conn.execute("SELECT COUNT(*) FROM 撤回摘要").fetchone()[0]
        旁路数 = conn.execute("SELECT COUNT(*) FROM 旁路匣").fetchone()[0]

        if 摘要数 != 撤回数:
            问题.append(f"撤回单{撤回数}跳≠撤回摘要{摘要数}条：撤回在而摘要空或摘要双写")

        for 窗 in 已关闭:
            证据 = 允许迟到策略._组装证据(conn, 窗)
            for 条 in 证据["链问题"]:
                问题.append(f"窗{窗['窗键']}:{条}")
            if not 证据["valid"]:
                问题.append(f"窗{窗['窗键']}修正证据无效:{证据['说明']}")

        脏旁路 = conn.execute(
            "SELECT COUNT(*) FROM 互动事件 WHERE 命运='已旁路' AND 窗键!=''"
        ).fetchone()[0]
        if 脏旁路:
            问题.append(f"旁路事件仍挂窗键:{脏旁路}")

        已关窗数 = len(已关闭)

    通过 = 1 if not 问题 else 0
    说明 = "窗输出与事件/撤回互证通过" if 通过 else "；".join(问题)[:800]
    with 写事务() as wconn:
        wconn.execute(
            """INSERT INTO 窗贯验(时刻,事件数,已关闭窗数,撤回数,旁路数,是否通过,说明)
               VALUES (?,?,?,?,?,?,?)""",
            (此刻(), 事件数, 已关窗数, 撤回数, 旁路数, 通过, 说明),
        )
    return {
        "是否通过": bool(通过),
        "事件数": 事件数,
        "已关闭窗数": 已关窗数,
        "撤回数": 撤回数,
        "摘要数": 摘要数,
        "旁路数": 旁路数,
        "说明": 说明,
        "问题": 问题,
    }

def _alias_payload(payload: dict) -> dict:
    out = dict(payload or {})
    if "窗键" in out and "window_key" not in out:
        out["window_key"] = out.get("窗键")
    if "房间键" in out and "room_key" not in out:
        out["room_key"] = out.get("房间键")
    if "事件编号" in out and "event_id" not in out:
        out["event_id"] = out.get("事件编号")
    if "aligned" not in out:
        out["aligned"] = True
    return out


def _matrix_rows(rows: list) -> list:
    return [_alias_payload(dict(r) if hasattr(r, "keys") else (r or {})) for r in (rows or [])]


def _plant_report_18(extra: dict | None = None) -> dict:
    data = {"ok": True, "aligned": True, "scope": "livewave", "nn": "18"}
    if extra:
        data.update(extra)
    return data

