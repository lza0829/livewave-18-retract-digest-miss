from datetime import datetime, timezone

from app.db import 连接, 写事务


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


建表 = """
CREATE TABLE IF NOT EXISTS 撤回摘要 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  窗键 TEXT NOT NULL,
  事件编号 TEXT NOT NULL DEFAULT '',
  旧合计 TEXT NOT NULL DEFAULT '',
  新合计 TEXT NOT NULL DEFAULT '',
  摘要哈希 TEXT NOT NULL DEFAULT '',
  链序号 INTEGER NOT NULL DEFAULT 0,
  撤回单号 INTEGER NOT NULL DEFAULT 0,
  批号 TEXT NOT NULL DEFAULT '',
  时刻 TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS 站规 (
  键 TEXT PRIMARY KEY,
  值 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 直播间 (
  房间键 TEXT PRIMARY KEY,
  标题 TEXT NOT NULL,
  主播 TEXT NOT NULL,
  开播事件时 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '直播中'
);
CREATE TABLE IF NOT EXISTS 互动事件 (
  事件编号 TEXT PRIMARY KEY,
  房间键 TEXT NOT NULL REFERENCES 直播间(房间键),
  事件类型 TEXT NOT NULL,
  事件时 TEXT NOT NULL,
  处理时 TEXT NOT NULL,
  观众键 TEXT NOT NULL DEFAULT '',
  点赞增量 INTEGER NOT NULL DEFAULT 0,
  送礼额 INTEGER NOT NULL DEFAULT 0,
  命运 TEXT NOT NULL DEFAULT '已入流',
  窗键 TEXT NOT NULL DEFAULT '',
  批次编号 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 装载批次 (
  编号 TEXT PRIMARY KEY,
  时刻 TEXT NOT NULL,
  报告 TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS 水位线 (
  房间键 TEXT PRIMARY KEY REFERENCES 直播间(房间键),
  事件时水位 TEXT NOT NULL,
  允许迟到秒 INTEGER NOT NULL DEFAULT 30,
  更新处理时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 热度窗 (
  窗键 TEXT PRIMARY KEY,
  房间键 TEXT NOT NULL REFERENCES 直播间(房间键),
  窗起事件时 TEXT NOT NULL,
  窗止事件时 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '开启',
  点赞合计 INTEGER NOT NULL DEFAULT 0,
  送礼合计 INTEGER NOT NULL DEFAULT 0,
  事件笔数 INTEGER NOT NULL DEFAULT 0,
  关闭处理时 TEXT NOT NULL DEFAULT '',
  版本 INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS 撤回单 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  窗键 TEXT NOT NULL,
  房间键 TEXT NOT NULL,
  原因 TEXT NOT NULL,
  旧点赞 INTEGER NOT NULL,
  新点赞 INTEGER NOT NULL,
  旧送礼 INTEGER NOT NULL,
  新送礼 INTEGER NOT NULL,
  旧笔数 INTEGER NOT NULL DEFAULT 0,
  新笔数 INTEGER NOT NULL DEFAULT 0,
  旧版本 INTEGER NOT NULL DEFAULT 0,
  新版本 INTEGER NOT NULL DEFAULT 0,
  处理时 TEXT NOT NULL,
  事件编号 TEXT NOT NULL DEFAULT '',
  批次编号 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 旁路匣 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  原因 TEXT NOT NULL,
  载荷 TEXT NOT NULL,
  时刻 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 窗贯验 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  时刻 TEXT NOT NULL,
  事件数 INTEGER NOT NULL,
  已关闭窗数 INTEGER NOT NULL,
  撤回数 INTEGER NOT NULL,
  旁路数 INTEGER NOT NULL,
  是否通过 INTEGER NOT NULL,
  说明 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS 互动事件_窗键 ON 互动事件(窗键, 命运);
CREATE INDEX IF NOT EXISTS 撤回单_窗键 ON 撤回单(窗键, 编号);
CREATE UNIQUE INDEX IF NOT EXISTS 撤回摘要_窗链 ON 撤回摘要(窗键, 链序号);
"""

# 老库补列：建表已含的新列对老库 ALTER 补上；新库自动跳过。
补列 = {
    "撤回单": {
        "旧笔数": "INTEGER NOT NULL DEFAULT 0",
        "新笔数": "INTEGER NOT NULL DEFAULT 0",
        "旧版本": "INTEGER NOT NULL DEFAULT 0",
        "新版本": "INTEGER NOT NULL DEFAULT 0",
    },
    "撤回摘要": {
        "撤回单号": "INTEGER NOT NULL DEFAULT 0",
    },
}


def _补列(conn, 表: str, 列: dict) -> None:
    已有 = {r[1] for r in conn.execute(f"PRAGMA table_info({表})").fetchall()}
    for 名, 型 in 列.items():
        if 名 not in 已有:
            conn.execute(f"ALTER TABLE {表} ADD COLUMN {名} {型}")


def _迁移旧撤回单(conn) -> None:
    """老库升级：旧撤回单没有版本/笔数（新列为 0），按窗键与编号顺序确定性回填。

    回填口径：关闭发射版 = 1，其后每次修正逐跳 +1；末跳新笔数取窗表现行笔数，
    向前倒推。只填空缺（新列仍为 0 的行），已写入的行一律不动。
    """
    for 窗行 in conn.execute("SELECT * FROM 热度窗").fetchall():
        行们 = conn.execute(
            "SELECT 编号 FROM 撤回单 WHERE 窗键=? AND 新版本=0 ORDER BY 编号",
            (窗行["窗键"],),
        ).fetchall()
        if not 行们:
            continue
        起 = conn.execute(
            "SELECT COALESCE(MAX(新版本),1) FROM 撤回单 WHERE 窗键=? AND 新版本>0",
            (窗行["窗键"],),
        ).fetchone()[0]
        笔 = int(窗行["事件笔数"])
        for k, r in enumerate(reversed(行们), start=1):
            新版本 = 起 + (len(行们) - k + 1)
            conn.execute(
                "UPDATE 撤回单 SET 旧版本=?, 新版本=?, 旧笔数=?, 新笔数=? WHERE 编号=?",
                (新版本 - 1, 新版本, 笔 - 1, 笔, r["编号"]),
            )
            笔 -= 1
        末版 = 起 + len(行们)
        if int(窗行["版本"]) < 末版:
            conn.execute(
                "UPDATE 热度窗 SET 版本=? WHERE 窗键=?", (末版, 窗行["窗键"])
            )


def 初始化库() -> None:
    建 = 连接()
    try:
        建.executescript(建表)
        for 表, 列 in 补列.items():
            _补列(建, 表, 列)
    finally:
        建.close()
    with 写事务() as conn:
        _迁移旧撤回单(conn)
        if conn.execute("SELECT COUNT(*) AS c FROM 站规").fetchone()["c"] == 0:
            for k, v in {
                "站名": "播浪",
                "窗长秒": "60",
                "允许迟到秒": "30",
                "水位推进策略": "事件时最大值",
                "关窗条件": "水位>=窗止即关闭发射",
                "旁路条件": "水位>=窗止+允许迟到",
                "迟到修正口径": "甲-原地改窗合计并写撤回单；撤回摘要链续写接管二次修正（缺摘要或链断整票失败）",
                "骨架": "互动事件入流→事件时间水位线推进→热度窗关闭发射→迟到修正撤回→窗输出与撤回互证",
            }.items():
                conn.execute("INSERT INTO 站规(键, 值) VALUES (?, ?)", (k, v))
        conn.execute(
            "INSERT OR IGNORE INTO 站规(键, 值) VALUES (?, ?)",
            ("迟到修正口径", "甲-原地改窗合计并写撤回单；撤回摘要链续写接管二次修正（缺摘要或链断整票失败）"),
        )
        if conn.execute("SELECT COUNT(*) AS c FROM 直播间").fetchone()["c"] == 0:
            conn.execute(
                "INSERT INTO 直播间(房间键, 标题, 主播, 开播事件时, 状态) VALUES (?,?,?,?,?)",
                ("房A", "晚间热聊", "主播小浪", "2026-11-22T12:00:00Z", "直播中"),
            )
            conn.execute(
                "INSERT INTO 水位线(房间键, 事件时水位, 允许迟到秒, 更新处理时) VALUES (?,?,?,?)",
                ("房A", "2026-11-22T12:00:00Z", 30, 此刻()),
            )


def 保证房间(conn, 房间键: str, 开播事件时: str = "2026-11-22T12:00:00Z") -> None:
    """演练用：幂等创建房间与水位线（调用方须在写事务内）。"""
    if not conn.execute("SELECT 1 FROM 直播间 WHERE 房间键=?", (房间键,)).fetchone():
        conn.execute(
            "INSERT INTO 直播间(房间键, 标题, 主播, 开播事件时, 状态) VALUES (?,?,?,?,?)",
            (房间键, f"演练房 {房间键}", "演练主播", 开播事件时, "直播中"),
        )
    if not conn.execute("SELECT 1 FROM 水位线 WHERE 房间键=?", (房间键,)).fetchone():
        默许 = conn.execute("SELECT 值 FROM 站规 WHERE 键='允许迟到秒'").fetchone()
        conn.execute(
            "INSERT INTO 水位线(房间键, 事件时水位, 允许迟到秒, 更新处理时) VALUES (?,?,?,?)",
            (房间键, 开播事件时, int(默许["值"]) if 默许 else 30, 此刻()),
        )
