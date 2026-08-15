import { useEffect, useState } from "react";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import client from "../api/client";
import ChartBox from "../components/ChartBox";
import { useI18n, formatNumber } from "../i18n";

const SEQ = ["var(--seq-1)", "var(--seq-2)", "var(--seq-3)", "var(--seq-4)",
             "var(--seq-5)", "var(--seq-6)", "var(--seq-7)"];

const pct = (x) => (x * 100).toFixed(1) + "%";

/** Ranglangan ustunli ro'yxat — ulush foizi har bir qatorda to'g'ridan-to'g'ri yozilgan. */
function BarList({ groups, colorFor }) {
  const { t, lang } = useI18n();
  if (!groups?.length) return <div className="empty">{t("dash.groupEmpty")}</div>;
  const max = Math.max(...groups.map((g) => g.amount));

  return (
    <div className="barlist">
      {groups.map((g, i) => (
        <div className="item" key={g.group_key}>
          <div className="top">
            {/* label berilgan bo'lsa o'shani ishlatamiz (kontragent nomi kabi
                tarjima qilinmaydigan qiymatlar uchun) */}
            <span className="nm">{g.label ?? t(`group.${g.group_key}`)}</span>
            <span className="amt">{formatNumber(g.amount, lang)}</span>
          </div>
          <div className="track">
            <div
              className="fill"
              style={{
                width: `${Math.max((g.amount / max) * 100, 0.6)}%`,
                background: colorFor ? colorFor(i) : SEQ[Math.min(i, SEQ.length - 1)],
              }}
            />
          </div>
          <div className="meta">
            <span className="pct">{pct(g.share)}</span>
            {g.transaction_count != null && (
              <span>{t("dash.opsCount", { n: g.transaction_count })}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { t, lang } = useI18n();
  const money = (n) => (n < 0 ? "−" : "") + formatNumber(n, lang);

  /** CFO ko'z bilan o'qish uchun: 2 004 668 863 -> "2.00 mlrd" */
  function compact(n) {
    const a = Math.abs(n);
    const sign = n < 0 ? "−" : "";
    if (a >= 1e9) return `${sign}${(a / 1e9).toFixed(2)} ${t("compact.bln")}`;
    if (a >= 1e6) return `${sign}${(a / 1e6).toFixed(1)} ${t("compact.mln")}`;
    if (a >= 1e3) return `${sign}${(a / 1e3).toFixed(0)} ${t("compact.thousand")}`;
    return `${sign}${Math.round(a)}`;
  }

  const [structure, setStructure] = useState(null);
  const [topOut, setTopOut] = useState([]);
  const [topIn, setTopIn] = useState([]);
  const [byCategory, setByCategory] = useState([]);
  const [risk, setRisk] = useState(null);
  const [periods, setPeriods] = useState(null);
  const [pending, setPending] = useState(0);
  const [error, setError] = useState("");
  const [currency, setCurrency] = useState(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [exporting, setExporting] = useState(false);

  const query = () => {
    const p = new URLSearchParams();
    if (currency) p.set("currency", currency);
    if (dateFrom) p.set("date_from", dateFrom);
    if (dateTo) p.set("date_to", dateTo);
    return p.toString();
  };

  useEffect(() => {
    const q = query();
    const sep = q ? `&${q}` : "";

    client.get(`/api/dashboard/structure${q ? `?${q}` : ""}`)
      .then((r) => setStructure(r.data))
      .catch(() => setError(t("dash.loadError")));
    client.get(`/api/dashboard/top-counterparties?limit=8&direction=out${sep}`).then((r) => setTopOut(r.data));
    client.get(`/api/dashboard/top-counterparties?limit=8&direction=in${sep}`).then((r) => setTopIn(r.data));
    client.get(`/api/dashboard/by-category${q ? `?${q}` : ""}`).then((r) => setByCategory(r.data)).catch(() => {});
    client.get(`/api/dashboard/concentration?direction=out&limit=8${sep}`).then((r) => setRisk(r.data)).catch(() => {});
    client.get(`/api/dashboard/periods${currency ? `?currency=${currency}` : ""}`)
      .then((r) => setPeriods(r.data)).catch(() => {});
    client.get("/api/transactions?review_status=pending_review&limit=1")
      .then((r) => setPending(r.data.pending_total))
      .catch(() => {});
  }, [currency, dateFrom, dateTo]);

  /** Excel faylni yuklab olish — token sarlavhada bo'lgani uchun blob orqali. */
  async function downloadExport(kind) {
    setExporting(true);
    try {
      const q = query();
      const res = await client.get(`/api/export/${kind}${q ? `?${q}` : ""}`, {
        responseType: "blob",
      });
      const disposition = res.headers["content-disposition"] || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = match ? match[1] : `${kind}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError(t("dash.exportError"));
    } finally {
      setExporting(false);
    }
  }

  if (error) return <div className="empty">{error}</div>;
  if (!structure) return <div className="empty">{t("common.loading")}</div>;

  const hasFilter = Boolean(dateFrom || dateTo);

  // Bo'sh natijaning ikki sababi bor va ular butunlay boshqacha:
  // umuman ma'lumot yo'q, yoki tanlangan davrda operatsiya yo'q.
  if (structure.period_start === null) {
    return (
      <section>
        <div className="page-head">
          <div><h1>{t("dash.title")}</h1><p>{t("common.noData")}</p></div>
        </div>
        {hasFilter ? (
          <>
            <DateFilter {...{ dateFrom, setDateFrom, dateTo, setDateTo, t }} />
            <div className="empty">{t("dash.noDataInPeriod")}</div>
          </>
        ) : (
          <div className="empty">{t("dash.noData")}</div>
        )}
      </section>
    );
  }

  // Valyuta backend'dan keladi — hisobot doimo bitta valyuta ichida yig'iladi
  const cur = structure.currency || t("currency");
  const multiCurrency = (structure.available_currencies || []).length > 1;

  const layerBy = (type) => structure.layers.find((l) => l.flow_type === type);
  const operating = layerBy("operating");
  const internal = layerBy("internal");

  const opNeg = structure.operating_net < 0;
  const covered = structure.financing_net > 0 && opNeg;

  const period = structure.period_start === structure.period_end
    ? structure.period_start
    : `${structure.period_start} — ${structure.period_end}`;

  // Kategoriya kesimi — faqat chiqim, ulush bilan. Ichki ko'chirmalar
  // kategoriyasi chiqarib tashlanadi: u xarajat emas.
  const expenseRows = byCategory.filter(
    (c) => c.direction === "out" && c.category_name !== "Hisoblar orasidagi ko'chirma"
  );
  const expenseTotal = expenseRows.reduce((s, c) => s + c.amount, 0);
  const expenseCategories = expenseRows.map((c) => ({
    group_key: c.category_name,
    label: c.category_name,
    amount: c.amount,
    share: expenseTotal ? c.amount / expenseTotal : 0,
    transaction_count: null,
  }));

  const totalOps = structure.layers.reduce(
    (s, l) => s + [...l.inflow_groups, ...l.outflow_groups]
      .reduce((a, g) => a + g.transaction_count, 0), 0);

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{t("dash.title")}</h1>
          <p>{period} · {t("dash.subtitle")}</p>
        </div>
        <div className="head-actions">
          {multiCurrency && (
            <div className="cur-switch">
              <span className="lbl">{t("dash.currencyLabel")}</span>
              {structure.available_currencies.map((c) => (
                <button
                  key={c}
                  className={c === structure.currency ? "active" : ""}
                  onClick={() => setCurrency(c)}
                >
                  {c}
                </button>
              ))}
            </div>
          )}
          <div className="export-group">
            <button className="btn-quiet" disabled={exporting}
                    onClick={() => downloadExport("dashboard")}>
              {t("dash.exportReport")}
            </button>
            <button className="btn-quiet" disabled={exporting}
                    onClick={() => downloadExport("transactions")}>
              {t("dash.exportTransactions")}
            </button>
          </div>
        </div>
      </div>

      <DateFilter {...{ dateFrom, setDateFrom, dateTo, setDateTo, t }} />

      {multiCurrency && (
        <div className="flag">
          <b>{t("dash.multiCurrencyTitle", { cur })}</b>
          {t("dash.multiCurrencyText")}
        </div>
      )}

      {/* Bosh xulosa — CFO birinchi bo'lib shuni o'qiydi */}
      <div className="verdict">
        <div>
          <div className="lead">{t("dash.heroLabel")}</div>
          <div className={`hero ${opNeg ? "neg" : "pos"}`}>{money(structure.operating_net)}</div>
          <div className="note">
            {opNeg
              ? t("dash.heroNeg", { amount: compact(Math.abs(structure.operating_net)), cur })
              : t("dash.heroPos", { amount: compact(structure.operating_net), cur })}
            {covered && t("dash.heroCovered", { amount: compact(structure.financing_net), cur })}
          </div>
        </div>
        <div className="side">
          <div className="k">{t("dash.inflow")}</div>
          <div className="v">{money(structure.operating_in)}</div>
          <div className="k">{t("dash.outflow")}</div>
          <div className="v">{money(structure.operating_out)}</div>
          <div className="k">{t("dash.operations")}</div>
          <div className="v">{totalOps}</div>
        </div>
      </div>

      {internal && (
        <div className="flag">
          <b>{t("dash.internalTitle", { amount: money(structure.internal_volume), cur })}</b>
          {t("dash.internalText")}
        </div>
      )}

      {pending > 0 && (
        <div className="flag">
          <b>{t("dash.pendingTitle", { n: pending })}</b>
          {t("dash.pendingText")}
        </div>
      )}

      {/* Davrlar taqqoslash — faqat ikki va undan ortiq davr bo'lganda.
          Bitta davrni o'zi bilan solishtirish ma'nosiz. */}
      {periods?.periods?.length >= 2 && (
        <>
          <div className="section-head">
            <h2>{t("dash.trendTitle")}</h2>
            <span className="hint">
              {t("dash.trendHint", { n: periods.periods.length })}
            </span>
          </div>
          <div className="layer-row">
            <DeltaTile label={t("dash.inflow")} value={periods.current.operating_in}
                       change={periods.change_in} money={money} t={t} positiveIsGood />
            <DeltaTile label={t("dash.outflow")} value={periods.current.operating_out}
                       change={periods.change_out} money={money} t={t} />
            <DeltaTile label={t("dash.heroLabel")} value={periods.current.operating_net}
                       change={periods.change_net} money={money} t={t} positiveIsGood />
          </div>
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-body">
              <ChartBox height={260}>
                {(width) => (
                <ComposedChart
                  width={width}
                  height={260}
                  data={periods.periods.map((p) => ({
                    period: String(p.period).slice(5),
                    inflow: p.operating_in,
                    outflow: -p.operating_out,
                    net: p.operating_net,
                  }))}
                  margin={{ top: 8, right: 8, left: 8, bottom: 4 }}
                >
                  <CartesianGrid stroke="#EFEBE0" vertical={false} />
                  <XAxis dataKey="period" fontSize={11} tickLine={false} stroke="#B4AE9E" />
                  <YAxis fontSize={11} tickLine={false} axisLine={false} stroke="#B4AE9E"
                         tickFormatter={(v) => (Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(0) + "M" : v)} />
                  <Tooltip formatter={(v, n) => [money(Math.abs(v)), t(`dash.series.${n}`)]}
                           contentStyle={{ border: "1px solid #DAD3C2", borderRadius: 0, fontSize: 12 }} />
                  <Legend formatter={(v) => t(`dash.series.${v}`)} wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="inflow" fill="#1b7fa8" barSize={14} />
                  <Bar dataKey="outflow" fill="#A6432E" barSize={14} />
                  <Line type="monotone" dataKey="net" stroke="#0F1B24" strokeWidth={2} dot={{ r: 3 }} />
                </ComposedChart>
                )}
              </ChartBox>
            </div>
          </div>
        </>
      )}

      {/* Uch qatlam */}
      <div className="section-head">
        <h2>{t("dash.layersTitle")}</h2>
        <span className="hint">{t("dash.layersHint")}</span>
      </div>
      <div className="layer-row">
        {["operating", "investing", "financing"].map((type) => {
          const l = layerBy(type);
          const net = l ? l.net : 0;
          const sign = net > 0 ? "pos" : net < 0 ? "neg" : "";
          return (
            <div className={`layer ${sign}`} key={type}>
              <div className="name">{t(`layer.${type}.name`)}</div>
              <div className="desc">{t(`layer.${type}.desc`)}</div>
              <div className={`net ${sign}`}>{l ? money(net) : "—"}</div>
              <div className="io">
                {l ? `+${compact(l.cash_in)} / −${compact(l.cash_out)}` : t("dash.noOps")}
              </div>
            </div>
          );
        })}
      </div>

      {/* XARAJATLAR TUZILMASI — asosiy bo'lim */}
      <div className="section-head">
        <h2>{t("dash.expenseTitle")}</h2>
        <span className="hint">
          {t("dash.expenseHint", { amount: money(structure.operating_out), cur })}
        </span>
      </div>
      <div className="card" style={{ marginBottom: 4 }}>
        <div className="card-body">
          <BarList groups={operating?.outflow_groups} />
        </div>
      </div>
      {operating?.outflow_groups?.[0]?.share > 0.5 && (
        <div className="flag warn" style={{ marginTop: 16 }}>
          <b>{t("dash.concentrationTitle")}</b>
          {t("dash.concentrationText", {
            group: t(`group.${operating.outflow_groups[0].group_key}`),
            pct: pct(operating.outflow_groups[0].share),
          })}
        </div>
      )}

      {/* Tushum tuzilmasi */}
      <div className="section-head">
        <h2>{t("dash.incomeTitle")}</h2>
        <span className="hint">
          {t("dash.incomeHint", { amount: money(structure.operating_in), cur })}
        </span>
      </div>
      <div className="card">
        <div className="card-body">
          <BarList groups={operating?.inflow_groups} colorFor={() => "var(--flow-pos)"} />
        </div>
      </div>

      {/* Moliyaviy va investitsion */}
      {["financing", "investing"].map((type) => {
        const l = layerBy(type);
        if (!l) return null;
        return (
          <div key={type}>
            <div className="section-head">
              <h2>{t(`layer.${type}.name`)}</h2>
              <span className="hint">{t("dash.netLabel", { amount: money(l.net), cur })}</span>
            </div>
            <div className="card">
              <div className="card-body" style={{ padding: "6px 0" }}>
                <div className="table-scroll">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>{t("table.direction")}</th>
                        <th>{t("table.group")}</th>
                        <th style={{ textAlign: "right" }}>{t("table.amount")}</th>
                        <th style={{ textAlign: "right" }}>{t("table.count")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {l.inflow_groups.map((g) => (
                        <tr key={"i" + g.group_key}>
                          <td><span className="tag in">{t("tag.in")}</span></td>
                          <td>{t(`group.${g.group_key}`)}</td>
                          <td className="mono" style={{ textAlign: "right" }}>{money(g.amount)}</td>
                          <td className="mono" style={{ textAlign: "right" }}>{g.transaction_count}</td>
                        </tr>
                      ))}
                      {l.outflow_groups.map((g) => (
                        <tr key={"o" + g.group_key}>
                          <td><span className="tag out">{t("tag.out")}</span></td>
                          <td>{t(`group.${g.group_key}`)}</td>
                          <td className="mono" style={{ textAlign: "right" }}>{money(g.amount)}</td>
                          <td className="mono" style={{ textAlign: "right" }}>{g.transaction_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        );
      })}

      {/* Boshqaruv kategoriyalari — provodka guruhlaridan farqli, bu buxgalter
          tasdiqlagan/tuzatgan talqin. Ikkalasi bir-birini to'ldiradi. */}
      {expenseCategories.length > 0 && (
        <>
          <div className="section-head">
            <h2>{t("dash.byCategoryTitle")}</h2>
            <span className="hint">{t("dash.byCategoryHint")}</span>
          </div>
          <div className="card">
            <div className="card-body">
              <BarList groups={expenseCategories} />
            </div>
          </div>
        </>
      )}

      {/* Konsentratsiya — "bitta kontragent yiqilsa nima bo'ladi" savoli */}
      {risk && risk.counterparty_count > 0 && (
        <>
          <div className="section-head">
            <h2>{t("dash.riskTitle")}</h2>
            <span className="hint">{t("dash.riskHint")}</span>
          </div>

          <div className="layer-row">
            <div className={`layer ${risk.top1_share > 0.3 ? "neg" : ""}`}>
              <div className="name">{t("dash.top1Label")}</div>
              <div className="desc">{t("dash.top1Desc")}</div>
              <div className={`net ${risk.top1_share > 0.3 ? "neg" : ""}`}>
                {pct(risk.top1_share)}
              </div>
              <div className="io">{risk.top_counterparties[0]?.name.slice(0, 30)}</div>
            </div>
            <div className={`layer ${risk.top3_share > 0.6 ? "neg" : ""}`}>
              <div className="name">{t("dash.top3Label")}</div>
              <div className="desc">{t("dash.top3Desc")}</div>
              <div className={`net ${risk.top3_share > 0.6 ? "neg" : ""}`}>
                {pct(risk.top3_share)}
              </div>
              <div className="io">{t("dash.ofTotal", { amount: compact(risk.total), cur })}</div>
            </div>
            <div className="layer">
              <div className="name">{t("dash.paretoLabel")}</div>
              <div className="desc">{t("dash.paretoDesc")}</div>
              <div className="net">{risk.counterparties_for_80pct}</div>
              <div className="io">{t("dash.ofCounterparties", { n: risk.counterparty_count })}</div>
            </div>
          </div>

          {risk.top1_share > 0.3 && (
            <div className="flag warn">
              <b>{t("dash.riskAlertTitle", {
                name: risk.top_counterparties[0].name,
                pct: pct(risk.top1_share),
              })}</b>
              {t("dash.riskAlertText")}
            </div>
          )}

          <div className="cp-row">
            <div className="card">
              <div className="card-head"><h3>{t("dash.riskTopTitle")}</h3></div>
              <div className="card-body">
                <BarList
                  groups={risk.top_counterparties.map((c) => ({
                    group_key: c.name,
                    label: c.name,
                    amount: c.amount,
                    share: c.share,
                    transaction_count: null,
                  }))}
                />
              </div>
            </div>
            <div className="card">
              <div className="card-head"><h3>{t("dash.largestTitle")}</h3></div>
              <div className="card-body" style={{ padding: "6px 0" }}>
                <div className="table-scroll">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>{t("import.colPeriod")}</th>
                        <th>{t("table.counterparty")}</th>
                        <th style={{ textAlign: "right" }}>{t("table.amount")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {risk.largest_payments.map((p, i) => (
                        <tr key={`${p.date}-${p.counterparty}-${i}`}>
                          <td className="mono" style={{ whiteSpace: "nowrap" }}>{p.date}</td>
                          <td>
                            {p.counterparty}
                            {p.category_name && <div className="src-line">{p.category_name}</div>}
                          </td>
                          <td className="mono" style={{ textAlign: "right" }}>{money(p.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Kontragentlar — ichki bank ko'chirmalari backend'da chiqarib tashlangan */}
      <div className="section-head">
        <h2>{t("dash.cpTitle")}</h2>
        <span className="hint">{t("dash.cpHint")}</span>
      </div>
      <div className="cp-row">
        <div className="card">
          <div className="card-head"><h3>{t("dash.cpPaid")}</h3></div>
          <div className="card-body" style={{ padding: "6px 0" }}>
            <CounterpartyTable rows={topOut} />
          </div>
        </div>
        <div className="card">
          <div className="card-head"><h3>{t("dash.cpReceived")}</h3></div>
          <div className="card-body" style={{ padding: "6px 0" }}>
            <CounterpartyTable rows={topIn} />
          </div>
        </div>
      </div>
    </section>
  );
}

/** Ko'rsatkich + oldingi davrga nisbatan o'zgarish. */
function DeltaTile({ label, value, change, money, t, positiveIsGood }) {
  const has = change !== null && change !== undefined;
  // Xarajatning o'sishi yomon, tushumning o'sishi yaxshi — shuning uchun
  // rang faqat ko'rsatkich ma'nosiga qarab beriladi
  const good = has && (positiveIsGood ? change >= 0 : change < 0);
  const arrow = has ? (change >= 0 ? "▲" : "▼") : "";

  return (
    <div className="layer">
      <div className="name">{label}</div>
      <div className="desc">{t("dash.vsPrevious")}</div>
      <div className="net">{money(value)}</div>
      <div className="io">
        {has ? (
          <span className={good ? "delta-good" : "delta-bad"}>
            {arrow} {Math.abs(change * 100).toFixed(1)}%
          </span>
        ) : t("dash.noPrevious")}
      </div>
    </div>
  );
}

function DateFilter({ dateFrom, setDateFrom, dateTo, setDateTo, t }) {
  const active = Boolean(dateFrom || dateTo);
  return (
    <div className="date-filter">
      <span className="lbl">{t("dash.periodLabel")}</span>
      <input type="date" value={dateFrom} max={dateTo || undefined}
             onChange={(e) => setDateFrom(e.target.value)} aria-label={t("dash.dateFrom")} />
      <span className="dash">—</span>
      <input type="date" value={dateTo} min={dateFrom || undefined}
             onChange={(e) => setDateTo(e.target.value)} aria-label={t("dash.dateTo")} />
      {active && (
        <button className="btn-quiet" onClick={() => { setDateFrom(""); setDateTo(""); }}>
          {t("dash.resetPeriod")}
        </button>
      )}
      {!active && <span className="hint-inline">{t("dash.allPeriods")}</span>}
    </div>
  );
}

function CounterpartyTable({ rows }) {
  const { t, lang } = useI18n();
  if (!rows?.length) return <div className="empty">{t("common.noData")}</div>;
  return (
    <div className="table-scroll">
      <table className="table">
        <thead>
          <tr>
            <th>#</th>
            <th>{t("table.counterparty")}</th>
            <th style={{ textAlign: "right" }}>{t("table.amount")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c, i) => (
            <tr key={c.counterparty}>
              <td className="mono">{String(i + 1).padStart(2, "0")}</td>
              <td>{c.counterparty}</td>
              <td className="mono" style={{ textAlign: "right" }}>{formatNumber(c.amount, lang)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
