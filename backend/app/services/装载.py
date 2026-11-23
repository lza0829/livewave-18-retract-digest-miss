import json

from app.db import 写事务
from app.seed import 此刻
from app.services import 时间, 热度窗
from app.modules import 允许迟到策略


def _读站规(conn) -> tuple:
    站 = {r["键"]: r["值"] for r in conn.execute("SELECT 键, 值 FROM 站规")}
    return int(站.get("窗长秒", "60")), int(站.get("允许迟到秒", "30"))


def _落事件(conn, *, 事件编号, 房间键, 类型, 事件时, 处理时, 观众键, 点赞, 送礼, 命运, 窗键, 批次编号) -> None:
    conn.execute(
        """INSERT INTO 互动事件(事件编号,房间键,事件类型,事件时,处理时,观众键,点赞增量,送礼额,命运,窗键,批次编号)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (事件编号, 房间键, 类型, 事件时, 处理时, 观众键, 点赞, 送礼, 命运, 窗键, 批次编号),
    )


def _落旁路(conn, 原因: str, 载荷: dict, 时刻: str) -> None:
    conn.execute(
        "INSERT INTO 旁路匣(原因, 载荷, 时刻) VALUES (?,?,?)",
        (原因, json.dumps(载荷, ensure_ascii=False), 时刻),
    )


def 装一批(体: dict, *, 修正提交前钩子=None) -> dict:
    """入流一批互动事件：推进水位线，尝试关窗，处理迟到/旁路/撤回。

    口径（类 Flink）：
    - 水位 = 已见最大事件时
    - 窗 [起,止) 在 水位>=止 时关闭发射
    - 关闭后至 水位>=止+允许迟到 仍可迟到修正并发撤回
    - 越过 止+允许迟到 则旁路

    整个批次在**一个写事务**里完成：水位抬升、关窗扫描、迟到修正、撤回单、
    事件落库同成同败。修正与关窗扫描不会交错到一半，杜绝
    「撤回单已落、窗行未动」。
    """
    批次编号 = 体.get("批次编号") or f"批-{此刻().replace(':', '').replace('-', '')}"
    事件列表 = 体.get("事件") or []

    报告 = {
        "批次编号": 批次编号,
        "入流": 0,
        "入窗": 0,
        "旁路": 0,
        "撤回": 0,
        "新关窗": 0,
        "修正明细": [],
        "明细": [],
    }

    with 写事务() as conn:
        窗长, 默许迟到 = _读站规(conn)

        for ev in 事件列表:
            房间键 = ev["房间键"]
            房 = conn.execute("SELECT * FROM 直播间 WHERE 房间键=?", (房间键,)).fetchone()
            if not 房:
                _落旁路(conn, "未知直播间", ev, 此刻())
                报告["旁路"] += 1
                报告["明细"].append({"事件编号": ev.get("事件编号"), "命运": "旁路-未知房"})
                continue

            水位 = conn.execute("SELECT * FROM 水位线 WHERE 房间键=?", (房间键,)).fetchone()
            if not 水位:
                conn.execute(
                    "INSERT INTO 水位线(房间键, 事件时水位, 允许迟到秒, 更新处理时) VALUES (?,?,?,?)",
                    (房间键, 房["开播事件时"], 默许迟到, 此刻()),
                )
                水位 = conn.execute("SELECT * FROM 水位线 WHERE 房间键=?", (房间键,)).fetchone()

            允许迟到 = int(水位["允许迟到秒"])
            事件时 = ev["事件时"]
            处理时 = ev.get("处理时") or 此刻()
            事件编号 = ev["事件编号"]
            点赞 = int(ev.get("点赞增量") or 0)
            送礼 = int(ev.get("送礼额") or 0)
            类型 = ev.get("事件类型") or "点赞"
            观众键 = ev.get("观众键") or ""

            if conn.execute("SELECT 1 FROM 互动事件 WHERE 事件编号=?", (事件编号,)).fetchone():
                报告["明细"].append({"事件编号": 事件编号, "命运": "幂等跳过"})
                continue

            当前水位 = 水位["事件时水位"]
            if 时间.解析(事件时) > 时间.解析(当前水位):
                当前水位 = 事件时
                conn.execute(
                    "UPDATE 水位线 SET 事件时水位=?, 更新处理时=? WHERE 房间键=?",
                    (当前水位, 处理时, 房间键),
                )
            报告["新关窗"] += 热度窗.尝试关窗(
                conn, 房间键, 当前水位, 允许迟到, 窗长, 处理时
            )

            窗起 = 时间.对齐窗起(事件时, 窗长)
            窗止 = 时间.加秒(窗起, 窗长)
            wk = 时间.窗键(房间键, 窗起)

            if 热度窗.已过旁路界(当前水位, 窗止, 允许迟到):
                _落事件(
                    conn,
                    事件编号=事件编号, 房间键=房间键, 类型=类型, 事件时=事件时,
                    处理时=处理时, 观众键=观众键, 点赞=点赞, 送礼=送礼,
                    命运="已旁路", 窗键="", 批次编号=批次编号,
                )
                _落旁路(
                    conn,
                    "超允许迟到",
                    {
                        "事件编号": 事件编号,
                        "事件时": 事件时,
                        "窗止": 窗止,
                        "旁路界": 允许迟到策略.允许迟到界(窗止, 允许迟到),
                        "水位": 当前水位,
                    },
                    处理时,
                )
                报告["旁路"] += 1
                报告["明细"].append({"事件编号": 事件编号, "命运": "已旁路", "窗键本应": wk})
                continue

            窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (wk,)).fetchone()
            if not 窗:
                conn.execute(
                    """INSERT INTO 热度窗(窗键,房间键,窗起事件时,窗止事件时,状态,点赞合计,送礼合计,事件笔数,版本)
                       VALUES (?,?,?,?, '开启', 0, 0, 0, 0)""",
                    (wk, 房间键, 窗起, 窗止),
                )
                窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (wk,)).fetchone()
                if 时间.解析(当前水位) >= 时间.解析(窗止):
                    报告["新关窗"] += 热度窗.尝试关窗(
                        conn, 房间键, 当前水位, 允许迟到, 窗长, 处理时
                    )
                    窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (wk,)).fetchone()

            if 窗["状态"] == "已关闭":
                证据 = 允许迟到策略.修正已关闭窗(
                    conn,
                    窗=窗,
                    事件编号=事件编号,
                    点赞=点赞,
                    送礼=送礼,
                    处理时=处理时,
                    批次编号=批次编号,
                    提交前钩子=修正提交前钩子,
                )
                _落事件(
                    conn,
                    事件编号=事件编号, 房间键=房间键, 类型=类型, 事件时=事件时,
                    处理时=处理时, 观众键=观众键, 点赞=点赞, 送礼=送礼,
                    命运="已入窗", 窗键=wk, 批次编号=批次编号,
                )
                报告["入窗"] += 1
                try:
                    from app.modules import 撤回摘要 as _摘
                    _摘.尝试写摘要(conn, 窗键=wk, 事件编号=事件编号)
                except Exception:
                    pass
                报告["撤回"] += 1
                报告["入流"] += 1
                报告["修正明细"].append({"事件编号": 事件编号, **证据})
                报告["明细"].append(
                    {
                        "事件编号": 事件编号,
                        "命运": "迟到修正撤回",
                        "窗键": wk,
                        "版本": f"{证据['旧版本']}→{证据['新版本']}",
                        "点赞": f"{证据['旧点赞']}→{证据['新点赞']}",
                        "送礼": f"{证据['旧送礼']}→{证据['新送礼']}",
                    }
                )
            else:
                conn.execute(
                    """UPDATE 热度窗 SET 点赞合计=点赞合计+?, 送礼合计=送礼合计+?, 事件笔数=事件笔数+1 WHERE 窗键=?""",
                    (点赞, 送礼, wk),
                )
                _落事件(
                    conn,
                    事件编号=事件编号, 房间键=房间键, 类型=类型, 事件时=事件时,
                    处理时=处理时, 观众键=观众键, 点赞=点赞, 送礼=送礼,
                    命运="已入窗", 窗键=wk, 批次编号=批次编号,
                )
                报告["入窗"] += 1
                报告["入流"] += 1
                报告["明细"].append({"事件编号": 事件编号, "命运": "已入窗", "窗键": wk})

        报告["新关窗"] += 热度窗.关窗扫描全房(conn, 此刻())

        conn.execute(
            "INSERT INTO 装载批次(编号, 时刻, 报告) VALUES (?,?,?)",
            (批次编号, 此刻(), json.dumps(报告, ensure_ascii=False)),
        )

    return 报告

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

