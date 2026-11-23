"""撤回摘要：首撤同票落摘要、二撤起以摘要链末跳为起点续写（甲口径·摘要链续写）。"""

import hashlib
import json

状态 = "已实现"

口径 = "甲-摘要链续写：首撤同票落摘要；二撤起以摘要末跳新合计为起点续写并升链序号；缺摘要或链断整票失败"


class 摘要违例(Exception):
    """摘要链缺失/断裂/与撤回单对不上：调用方据此整批回滚。"""


def 合计串(点赞: int, 送礼: int, 笔数: int) -> str:
    """旧→新合计的确定性串形：落库与核证重算共用同一口径。"""
    return json.dumps(
        {"点赞": int(点赞), "送礼": int(送礼), "笔数": int(笔数)},
        ensure_ascii=False,
        sort_keys=True,
    )


def 读合计(串: str) -> dict:
    try:
        d = json.loads(串)
        return {"点赞": int(d["点赞"]), "送礼": int(d["送礼"]), "笔数": int(d["笔数"])}
    except Exception:
        return {}


def 算哈希(*, 窗键: str, 事件编号: str, 旧合计: str, 新合计: str, 链序号: int, 撤回单号: int) -> str:
    """摘要哈希绑定撤回单号：摘要与撤回单一一对应，对不上即核证失败。"""
    料 = "|".join([str(窗键), str(事件编号), str(旧合计), str(新合计), str(int(链序号)), str(int(撤回单号))])
    return hashlib.sha256(料.encode("utf-8")).hexdigest()


def 链(conn, 窗键: str) -> list:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM 撤回摘要 WHERE 窗键=? ORDER BY 链序号", (窗键,)
        ).fetchall()
    ]


def 末跳(conn, 窗键: str):
    return conn.execute(
        "SELECT * FROM 撤回摘要 WHERE 窗键=? ORDER BY 链序号 DESC LIMIT 1", (窗键,)
    ).fetchone()


def 写摘要(conn, *, 窗键, 事件编号, 旧合计, 新合计, 链序号, 撤回单号, 批号, 时刻) -> str:
    """与撤回单同票落摘要（同一写事务）：链序号接续，哈希绑定撤回单号。

    （窗键, 链序号）有唯一索引：同序号双写直接约束失败，整批回滚。
    """
    哈希 = 算哈希(
        窗键=窗键, 事件编号=事件编号, 旧合计=旧合计, 新合计=新合计,
        链序号=链序号, 撤回单号=撤回单号,
    )
    游标 = conn.execute(
        """INSERT INTO 撤回摘要(窗键,事件编号,旧合计,新合计,摘要哈希,链序号,撤回单号,批号,时刻)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (窗键, 事件编号, 旧合计, 新合计, 哈希, int(链序号), int(撤回单号), 批号, 时刻),
    )
    if 游标.rowcount != 1:
        raise 摘要违例(f"窗{窗键}摘要未落，整批回滚")
    return 哈希


def 对账窗(conn, 窗) -> dict:
    """单窗三面对账：摘要链 ↔ 撤回单链 ↔ 窗行。问题为空即钉死。

    甲口径形态不变量：同一关闭窗恰好 1 个摘要根（链序号 1..N 连续一条链），
    每跳摘要的事件/合计/哈希与对应撤回单一致，末跳新合计 = 窗表现行合计。
    """
    窗键 = 窗["窗键"]
    撤回们 = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM 撤回单 WHERE 窗键=? ORDER BY 编号", (窗键,)
        ).fetchall()
    ]
    摘要们 = 链(conn, 窗键)
    问题 = []
    根数 = sum(1 for s in 摘要们 if int(s["链序号"]) == 1)

    if 撤回们 and not 摘要们:
        问题.append(f"撤回单{len(撤回们)}跳在、摘要空：首撤未同票落摘要")
    if 摘要们 and not 撤回们:
        问题.append(f"摘要{len(摘要们)}条悬空：无对应撤回单")
    if 摘要们:
        if 根数 != 1:
            问题.append(f"摘要根数{根数}≠1：甲口径同一关闭窗只认一条链")
        序号列 = [int(s["链序号"]) for s in 摘要们]
        if 序号列 != list(range(1, len(摘要们) + 1)):
            问题.append(f"摘要链序号断裂:{序号列}")
    if 撤回们 and 摘要们 and len(撤回们) != len(摘要们):
        问题.append(f"撤回单{len(撤回们)}跳≠摘要{len(摘要们)}条")

    for k, (撤, 摘) in enumerate(zip(撤回们, 摘要们), start=1):
        旧 = 合计串(撤["旧点赞"], 撤["旧送礼"], 撤["旧笔数"])
        新 = 合计串(撤["新点赞"], 撤["新送礼"], 撤["新笔数"])
        if int(摘["撤回单号"]) != int(撤["编号"]):
            问题.append(f"第{k}跳摘要撤回单号{摘['撤回单号']}≠撤回单{撤['编号']}")
        if 摘["事件编号"] != 撤["事件编号"]:
            问题.append(f"第{k}跳摘要事件{摘['事件编号']}≠撤回单事件{撤['事件编号']}")
        if 摘["旧合计"] != 旧 or 摘["新合计"] != 新:
            问题.append(f"第{k}跳摘要合计与撤回单对不上")
        期望 = 算哈希(
            窗键=窗键, 事件编号=撤["事件编号"], 旧合计=旧, 新合计=新,
            链序号=k, 撤回单号=撤["编号"],
        )
        if 摘["摘要哈希"] != 期望:
            问题.append(f"第{k}跳摘要哈希与撤回单对不上")
        if k > 1 and 摘["旧合计"] != 摘要们[k - 2]["新合计"]:
            问题.append(f"第{k}跳旧合计≠上一跳新合计：链断")

    if 摘要们:
        末新 = 读合计(摘要们[-1]["新合计"])
        现行 = {
            "点赞": int(窗["点赞合计"]),
            "送礼": int(窗["送礼合计"]),
            "笔数": int(窗["事件笔数"]),
        }
        if 末新 != 现行:
            问题.append(f"摘要末跳新合计{末新}≠窗表现行{现行}：窗被绕开摘要改歪")

    return {
        "窗键": 窗键,
        "根数": 根数,
        "链序号": [int(s["链序号"]) for s in 摘要们],
        "摘要链": 摘要们,
        "撤回跳数": len(撤回们),
        "问题": 问题,
        "钉死": not 问题,
    }


def 续写起点(conn, 窗) -> dict:
    """第二笔及以后迟到的唯一起点：摘要链末跳新合计；缺摘要或链断即违例。

    窗行现值必须等于摘要末跳新合计——不等说明窗被绕开摘要改过，同样违例。
    """
    对 = 对账窗(conn, 窗)
    if not 对["摘要链"]:
        raise 摘要违例(f"窗{窗['窗键']}已有撤回单但摘要为空：禁止绕开摘要续写")
    if 对["问题"]:
        raise 摘要违例("；".join(对["问题"]))
    末新 = 读合计(对["摘要链"][-1]["新合计"])
    return {**末新, "链序号": 对["链序号"][-1] + 1}


def 应拒缺摘要(conn, 窗键: str) -> bool:
    """该窗已有撤回单但摘要缺失/链断/对不上 → 后续修正必须拒写。"""
    窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (窗键,)).fetchone()
    if not 窗:
        return False
    撤数 = conn.execute(
        "SELECT COUNT(*) FROM 撤回单 WHERE 窗键=?", (窗键,)
    ).fetchone()[0]
    if 撤数 == 0:
        return False
    return bool(对账窗(conn, 窗)["问题"])


def 核证(conn, 窗键: str | None = None) -> dict:
    """撤回摘要核证（只读）：逐窗三面对账 + 全局撤回/摘要跳数对账。

    钉死 = 所有挂撤回/摘要的窗都满足甲口径形态不变量，且全局跳数相等。
    """
    if 窗键:
        键集 = [窗键]
    else:
        键集 = [
            r[0]
            for r in conn.execute(
                "SELECT 窗键 FROM 撤回单 UNION SELECT 窗键 FROM 撤回摘要 ORDER BY 1"
            ).fetchall()
        ]
    窗报 = []
    问题 = []
    for k in 键集:
        窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (k,)).fetchone()
        if not 窗:
            问题.append(f"窗{k}不存在但挂有撤回/摘要")
            窗报.append({"窗键": k, "钉死": False, "问题": ["窗不存在"], "摘要链": [], "根数": 0, "链序号": [], "撤回跳数": 0})
            continue
        对 = 对账窗(conn, 窗)
        窗报.append(对)
        问题.extend(f"窗{k}:{p}" for p in 对["问题"])
    撤总 = conn.execute("SELECT COUNT(*) FROM 撤回单").fetchone()[0]
    摘总 = conn.execute("SELECT COUNT(*) FROM 撤回摘要").fetchone()[0]
    if 撤总 != 摘总:
        问题.append(f"全局撤回单{撤总}跳≠撤回摘要{摘总}条")
    return {
        "口径": 口径,
        "采信": "摘要链末跳（二次修正唯一起点，不按裸窗行另算）",
        "钉死": not 问题,
        "窗数": len(窗报),
        "撤回跳数": 撤总,
        "摘要条数": 摘总,
        "问题": 问题,
        "窗": 窗报,
    }
