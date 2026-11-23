import React, { useEffect, useState } from "react";
import { 取, 递 } from "../api.js";

export default function 迟到修正页() {
  const [列, 设列] = useState([]);
  const [选, 设选] = useState("");
  const [证, 设证] = useState(null);
  const [演, 设演] = useState(null);
  const [忙, 设忙] = useState(false);
  const 刷 = () => 取("/迟到修正").then((r) => {
    设列(r);
    if (!选 && r.length) 选一(r[0].窗键);
  });
  const 选一 = async (k) => {
    设选(k);
    设证(await 取(`/迟到修正/明细?窗键=${encodeURIComponent(k)}`));
  };
  useEffect(() => { 刷(); }, []);
  const 跑 = async () => {
    设忙(true);
    try {
      设演(await 递("/演练/迟到修正"));
      await 刷();
      if (选) await 选一(选);
    } finally {
      设忙(false);
    }
  };
  const 标 = (v) => (v ? <span className="徽章 通">valid</span> : <span className="徽章 败">无效</span>);
  const 段 = (名, x) =>
    x && (
      <div className="卡板">
        <div className="段题">
          {名}{" "}
          <span className={`徽章 ${x.通过 ? "通" : "败"}`}>{x.通过 ? "通过" : "失败"}</span>
        </div>
        <div className="述" style={{ margin: 0 }}>
          {Array.isArray(x.说明) ? x.说明.map((s, i) => <div key={i}>{s}</div>) : x.说明}
        </div>
        {x.撤回链 && (
          <table style={{ marginTop: "0.6rem" }}>
            <thead>
              <tr><th>编号</th><th>旧版本→新版本</th><th>点赞旧→新</th><th>送礼旧→新</th><th>笔数</th><th>触发事件</th></tr>
            </thead>
            <tbody>
              {x.撤回链.map((r) => (
                <tr key={r.编号}>
                  <td>{r.编号}</td>
                  <td className="码">{r.旧版本} → {r.新版本}</td>
                  <td>{r.旧点赞} → {r.新点赞}</td>
                  <td>{r.旧送礼} → {r.新送礼}</td>
                  <td>{r.旧笔数} → {r.新笔数}</td>
                  <td className="码">{r.事件编号}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {x.历史合计三档 && (
          <div className="码" style={{ marginTop: "0.5rem" }}>
            {x.历史合计三档.map((p) => `v${p.版本} 赞${p.点赞}/送${p.送礼}/笔${p.笔数}`).join("  →  ")}
          </div>
        )}
        {x.半截检出?.length > 0 && (
          <div className="码" style={{ color: "var(--败)", marginTop: "0.5rem" }}>{x.半截检出.join("；")}</div>
        )}
      </div>
    );
  return (
    <div>
      <h1 className="题">迟到修正</h1>
      <p className="述">
        口径：<strong>甲——原地改窗合计并写撤回单</strong>。允许迟到界（窗止 + 允许迟到）内落进已关闭窗的事件，
        就地抬升窗表的点赞/送礼/笔数并升高版本，同时写一笔撤回单（旧值→新值、旧版本→新版本、触发事件）。
        窗表只留当前合计；历史旧合计经撤回链逐跳回溯。改窗与写撤回单同事务，不接受「撤回已落、窗未动」。
      </p>
      <div className="行">
        <button className="水" onClick={跑} disabled={忙}>{忙 ? "演练中…" : "跑迟到修正演练"}</button>
        <button className="次" onClick={刷}>刷新修正列表</button>
      </div>
      {演 && (
        <>
          <div className={`证旗 ${演.全部通过 ? "通" : "败"}`} style={{ marginBottom: "0.9rem" }}>
            <div className="标">{演.全部通过 ? "演练通过" : "演练失败"}</div>
            <div className="辅">
              一：首次迟到合计必变 + 撤回证据；
              二：二次迟到版本升高、撤回链两跳；
              三：修正与抬水位并发不半截；
              四：注入故障后整批回滚。
            </div>
          </div>
          <div className="卡板">
            {段("步骤一 · 首窗后首次迟到", 演.步骤一_首窗后首次迟到)}
            {段("步骤二 · 第二次迟到", 演.步骤二_第二次迟到)}
            {段("步骤三 · 修正与抬水位并发", 演.步骤三_修正与抬水位并发)}
            {段("步骤四 · 故障注入同成败", 演.步骤四_故障注入同成败)}
          </div>
        </>
      )}
      <div className="段">
        <div className="段题">已关闭窗修正证据</div>
        {!列.length ? (
          <div className="空态">暂无已关闭窗。先推准时样例关一窗，再灌迟到修正样例。</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>窗键</th><th>允许迟到界</th><th>水位</th><th>版本</th>
                <th>修正次数</th><th>当前合计</th><th>证据</th><th></th>
              </tr>
            </thead>
            <tbody>
              {列.map((r) => (
                <tr key={r.窗键} className={选 === r.窗键 ? "亮行" : ""}>
                  <td className="码">{r.窗键}</td>
                  <td className="码">{r.允许迟到界}</td>
                  <td className="码">{r.水位}</td>
                  <td>{r.版本}</td>
                  <td>{r.修正次数}</td>
                  <td>赞{r.当前合计.点赞}/送{r.当前合计.送礼}/笔{r.当前合计.笔数}</td>
                  <td>{标(r.valid)}</td>
                  <td><button className="次" onClick={() => 选一(r.窗键)}>看证据</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {证 && (
        <div className="段">
          <div className="段题">单窗证据 · {证.窗键}</div>
          <div className="述" style={{ marginBottom: "0.5rem" }}>
            {证.状态} · 版本 {证.版本} · 基础版本 {证.基础版本} · 修正 {证.修正次数} 次 ·{" "}
            {证.可再修正 ? "仍在允许迟到界内" : "已越允许迟到界"} · {标(证.valid)}
          </div>
          <div className="提示条">{证.历史旧值查询方式}</div>
          <table>
            <thead>
              <tr><th>版本</th><th>点赞</th><th>送礼</th><th>笔数</th><th>来源</th><th>触发事件</th></tr>
            </thead>
            <tbody>
              {证.历史合计.map((p) => (
                <tr key={p.版本}>
                  <td>v{p.版本}</td><td>{p.点赞}</td><td>{p.送礼}</td><td>{p.笔数}</td>
                  <td>{p.来源}</td><td className="码">{p.触发事件 || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!证.撤回链.length ? (
            <div className="空态">该窗尚无迟到修正。</div>
          ) : (
            <table style={{ marginTop: "0.6rem" }}>
              <thead>
                <tr><th>编号</th><th>旧版本→新版本</th><th>点赞旧→新</th><th>送礼旧→新</th><th>笔数旧→新</th><th>触发事件</th><th>批次</th><th>处理时</th></tr>
              </thead>
              <tbody>
                {证.撤回链.map((r) => (
                  <tr key={r.编号}>
                    <td>{r.编号}</td>
                    <td className="码">{r.旧版本} → {r.新版本}</td>
                    <td>{r.旧点赞} → {r.新点赞}</td>
                    <td>{r.旧送礼} → {r.新送礼}</td>
                    <td>{r.旧笔数} → {r.新笔数}</td>
                    <td className="码">{r.事件编号}</td>
                    <td className="码">{r.批次编号 || "—"}</td>
                    <td className="码">{r.处理时}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {证.链问题.length > 0 && (
            <div className="码" style={{ color: "var(--败)" }}>链问题：{证.链问题.join("；")}</div>
          )}
        </div>
      )}
    </div>
  );
}
