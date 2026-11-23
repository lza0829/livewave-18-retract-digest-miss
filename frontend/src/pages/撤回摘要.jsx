import React, { useEffect, useState } from "react";
import { 取 } from "../api.js";

export default function 撤回摘要() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const reload = () => {
    取("/核证/撤回摘要").then(setData).catch((e) => setErr(String(e.message || e)));
  };
  useEffect(() => { reload(); }, []);
  return (
    <div>
      <h1 className="题">撤回摘要核证</h1>
      <p className="述">
        只读核证：摘要链 ↔ 撤回单 ↔ 窗行三面对账。逐跳重算摘要哈希、校验单根形态与链序号连续、
        末跳新合计须等于窗表现行；全部通过即<strong>钉死</strong>。
        二次迟到修正只采信摘要链末跳，不按裸窗行另算。
      </p>
      {err && <pre className="码">{err}</pre>}
      <div className="行">
        <button className="次" onClick={reload}>刷新</button>
      </div>
      {data && (
        <>
          <div className={`证旗 ${data.钉死 ? "通" : "败"}`} style={{ marginBottom: "0.9rem" }}>
            <div className="标">{data.钉死 ? "钉死" : "未钉死"}</div>
            <div className="辅">
              {data.口径} · 核证窗 {data.窗数} · 撤回 {data.撤回跳数} 跳 · 摘要 {data.摘要条数} 条
            </div>
          </div>
          {data.问题?.length > 0 && (
            <pre className="码" style={{ color: "var(--败)" }}>{data.问题.join("\n")}</pre>
          )}
          <div className="段">
            <div className="段题">逐窗对账</div>
            {!data.窗?.length ? (
              <div className="空态">尚无撤回/摘要。先灌准时样例关窗，再连打两笔迟到样例。</div>
            ) : (
              <table>
                <thead>
                  <tr><th>窗键</th><th>根数</th><th>链序号</th><th>撤回跳数</th><th>状态</th></tr>
                </thead>
                <tbody>
                  {data.窗.map((w) => (
                    <tr key={w.窗键}>
                      <td className="码">{w.窗键}</td>
                      <td>{w.根数}</td>
                      <td className="码">{(w.链序号 || []).join(" → ")}</td>
                      <td>{w.撤回跳数}</td>
                      <td>{w.钉死 ? <span className="徽章 通">钉死</span> : <span className="徽章 败">撕裂</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="段">
            <div className="段题">原始载荷</div>
            <pre className="码">{JSON.stringify(data, null, 2)}</pre>
          </div>
        </>
      )}
    </div>
  );
}
