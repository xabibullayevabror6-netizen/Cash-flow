import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ComposedChart, Area, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine,
} from "recharts";
import client from "../api/client";
import ChartBox from "../components/ChartBox";
import { useI18n, formatNumber } from "../i18n";

const WEEKDAYS = ["0", "1", "2", "3", "4"];

export default function ForecastPage() {
  const { t, lang } = useI18n();
  const money = (n) => (n < 0 ? "−" : "") + formatNumber(n, lang);

  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  // Stsenariy: tushum shu koeffitsientga ko'paytiriladi
  const [collections, setCollections] = useState(1.0);

  useEffect(() => {
    client.get(`/api/forecast?weeks=13&collections_factor=${collections}`)
      .then((r) => setData(r.data))
      .catch(() => setError(t("common.error")));
  }, [collections]);

  if (error) return <div className="empty">{error}</div>;
  if (!data) return <div className="empty">{t("common.loading")}</div>;

  const cur = data.currency || t("currency");

  // Tarix yetarli emas — sababi va nima qilish kerakligi ko'rsatiladi
  if (!data.sufficient) {
    return (
      <section>
        <div className="page-head">
          <div>
            <h1>{t("forecast.title")}</h1>
            <p>{t("forecast.subtitle")}</p>
          </div>
        </div>
        <div className="flag warn">
          <b>{t("forecast.insufficientTitle")}</b>
          {t("forecast.insufficientDays", {
            have: data.business_days_of_history,
            need: data.min_days_required,
          })}
        </div>
        <div className="card">
          <div className="card-body">
            <p style={{ fontSize: 13.5, lineHeight: 1.65, marginBottom: 16 }}>
              {t("forecast.howToFix")}
            </p>
            <Link to="/import" className="btn-primary"
                  style={{ display: "inline-block", textDecoration: "none" }}>
              {t("forecast.goImport")}
            </Link>
          </div>
        </div>
      </section>
    );
  }

  const chartData = data.items.map((f) => ({
    week: String(f.forecast_week_start).slice(5),
    inflow: f.predicted_cash_in,
    outflow: -f.predicted_cash_out,
    balance: f.predicted_balance,
    // Area uchun: pastki chegara va oraliq balandligi (stacked ko'rinish)
    bandLow: f.balance_p10,
    bandRange: f.balance_p90 - f.balance_p10,
  }));

  const last = data.items[data.items.length - 1];
  const dailyNet = data.avg_daily_in * data.collections_factor - data.avg_daily_out;
  const negativeWeek = data.items.find((f) => f.predicted_balance < 0);
  const riskyWeek = data.items.find((f) => f.balance_p10 < 0);

  const accuracy = data.accuracy_mape;
  const accuracyLevel =
    accuracy == null ? "unknown"
      : accuracy <= 0.2 ? "good"
      : accuracy <= 0.4 ? "medium"
      : "weak";

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{t("forecast.title")}</h1>
          <p>
            {t("forecast.basedOnDays", { days: data.business_days_of_history })}
            {" · "}{data.history_start} — {data.history_end}{" · "}{cur}
          </p>
        </div>
        <div className="head-actions">
          <div className="scenario">
            <span className="lbl">{t("forecast.scenario")}</span>
            {[
              { v: 0.8, l: "−20%" },
              { v: 0.9, l: "−10%" },
              { v: 1.0, l: t("forecast.base") },
            ].map((o) => (
              <button key={o.v}
                      className={Math.abs(collections - o.v) < 0.001 ? "active" : ""}
                      onClick={() => setCollections(o.v)}>
                {o.l}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Ishonchlilik — foydalanuvchi prognozga qanchalik ishonishini bilishi kerak */}
      <div className={`flag ${accuracyLevel === "weak" ? "warn" : ""}`}>
        <b>
          {accuracy == null
            ? t("forecast.accuracyUnknown")
            : t("forecast.accuracyTitle", {
                pct: (accuracy * 100).toFixed(0),
                level: t(`forecast.accuracy.${accuracyLevel}`),
              })}
        </b>
        {t("forecast.accuracyText")}
      </div>

      {!data.has_opening_balance && (
        <div className="flag warn">
          <b>{t("forecast.noBalanceTitle")}</b>
          {t("forecast.noBalanceText")}{" "}
          <Link to="/bank-accounts">{t("forecast.noBalanceCta")}</Link>
        </div>
      )}

      <div className="layer-row">
        <div className={`layer ${dailyNet >= 0 ? "pos" : "neg"}`}>
          <div className="name">{t("forecast.dailyNet")}</div>
          <div className="desc">{t("forecast.dailyNetDesc")}</div>
          <div className={`net ${dailyNet >= 0 ? "pos" : "neg"}`}>{money(dailyNet)}</div>
          <div className="io">
            +{formatNumber(data.avg_daily_in * data.collections_factor, lang)}
            {" / −"}{formatNumber(data.avg_daily_out, lang)}
          </div>
        </div>
        <div className={`layer ${last.predicted_balance >= 0 ? "pos" : "neg"}`}>
          <div className="name">
            {data.has_opening_balance ? t("forecast.endBalance") : t("forecast.endFlow")}
          </div>
          <div className="desc">{t("forecast.endBalanceDesc", { n: data.items.length })}</div>
          <div className={`net ${last.predicted_balance >= 0 ? "pos" : "neg"}`}>
            {money(last.predicted_balance)}
          </div>
          <div className="io">
            {/* money() ishlatiladi, formatNumber emas: oxirgisi Math.abs qiladi
                va manfiy P10 musbatdek ko'rinib qoladi */}
            {t("forecast.range", {
              low: money(last.balance_p10),
              high: money(last.balance_p90),
            })}
          </div>
        </div>
        <div className={`layer ${riskyWeek ? "neg" : ""}`}>
          <div className="name">{t("forecast.riskLabel")}</div>
          <div className="desc">{t("forecast.riskDesc")}</div>
          <div className={`net ${riskyWeek ? "neg" : ""}`}>
            {riskyWeek ? String(riskyWeek.forecast_week_start) : t("forecast.noRisk")}
          </div>
          <div className="io">
            {negativeWeek
              ? t("forecast.medianNegative", { date: negativeWeek.forecast_week_start })
              : t("forecast.medianPositive")}
          </div>
        </div>
      </div>

      {riskyWeek && (
        <div className="flag warn">
          <b>{t("forecast.alertTitle", { date: riskyWeek.forecast_week_start })}</b>
          {t("forecast.alertText")}
        </div>
      )}

      {/* Yelpig'ich grafik: P10-P90 oralig'i + markaziy chiziq */}
      <div className="section-head">
        <h2>{t("forecast.chartTitle")}</h2>
        <span className="hint">{t("forecast.chartHint")}</span>
      </div>
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-body">
          <ChartBox height={340}>
            {(width) => (
              <ComposedChart width={width} height={340} data={chartData}
                             margin={{ top: 8, right: 8, left: 8, bottom: 4 }}>
                <CartesianGrid stroke="#EFEBE0" vertical={false} />
                <XAxis dataKey="week" fontSize={11} tickLine={false} stroke="#B4AE9E" />
                <YAxis fontSize={11} tickLine={false} axisLine={false} stroke="#B4AE9E"
                       tickFormatter={(v) => (Math.abs(v) >= 1e9 ? (v / 1e9).toFixed(1) + "B"
                                            : Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(0) + "M" : v)} />
                <Tooltip
                  formatter={(v, n) => {
                    if (n === "bandLow" || n === "bandRange") return null;
                    return [money(Math.abs(v)), t(`forecast.series.${n}`)];
                  }}
                  contentStyle={{ border: "1px solid #DAD3C2", borderRadius: 0, fontSize: 12 }}
                />
                <Legend formatter={(v) => t(`forecast.series.${v}`)}
                        wrapperStyle={{ fontSize: 12 }} />
                <ReferenceLine y={0} stroke="#A6432E" strokeDasharray="3 3" />

                {/* Noaniqlik oralig'i — ko'rinmas asos + rangli bo'lak */}
                <Area dataKey="bandLow" stackId="band" stroke="none" fill="none" legendType="none" />
                <Area dataKey="bandRange" stackId="band" stroke="none"
                      fill="#1b7fa8" fillOpacity={0.14} />

                <Bar dataKey="inflow" fill="#1b7fa8" barSize={9} />
                <Bar dataKey="outflow" fill="#A6432E" barSize={9} />
                <Line type="monotone" dataKey="balance" stroke="#0F1B24"
                      strokeWidth={2.5} dot={{ r: 3 }} />
              </ComposedChart>
            )}
          </ChartBox>
        </div>
      </div>

      {/* Muntazam to'lovlar — prognozning eng ishonchli qismi */}
      {(data.recurring_outflows.length > 0 || data.recurring_inflows.length > 0) && (
        <>
          <div className="section-head">
            <h2>{t("forecast.recurringTitle")}</h2>
            <span className="hint">{t("forecast.recurringHint")}</span>
          </div>
          <div className="cp-row">
            {[
              { rows: data.recurring_outflows, title: t("forecast.recurringOut") },
              { rows: data.recurring_inflows, title: t("forecast.recurringIn") },
            ].map((block) => (
              <div className="card" key={block.title}>
                <div className="card-head"><h3>{block.title}</h3></div>
                <div className="card-body" style={{ padding: "6px 0" }}>
                  {block.rows.length === 0 ? (
                    <div className="empty">{t("common.noData")}</div>
                  ) : (
                    <div className="table-scroll">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>{t("table.counterparty")}</th>
                            <th style={{ textAlign: "right" }}>{t("forecast.medianPerDay")}</th>
                            <th style={{ textAlign: "right" }}>{t("forecast.frequency")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {block.rows.map((r) => (
                            <tr key={r.counterparty}>
                              <td>{r.counterparty}</td>
                              <td className="mono" style={{ textAlign: "right" }}>
                                {formatNumber(r.median_amount, lang)}
                              </td>
                              <td className="mono" style={{ textAlign: "right" }}>
                                {(r.day_share * 100).toFixed(0)}%
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Haftalar jadvali */}
      <div className="section-head">
        <h2>{t("forecast.tableTitle")}</h2>
      </div>
      <div className="card">
        <div className="card-body" style={{ padding: "6px 0" }}>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("forecast.week")}</th>
                  <th style={{ textAlign: "right" }}>{t("forecast.inflow")}</th>
                  <th style={{ textAlign: "right" }}>{t("forecast.outflow")}</th>
                  <th style={{ textAlign: "right" }}>{t("forecast.p10")}</th>
                  <th style={{ textAlign: "right" }}>{t("forecast.balance")}</th>
                  <th style={{ textAlign: "right" }}>{t("forecast.p90")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((f) => (
                  <tr key={f.forecast_week_start}>
                    <td className="mono">{f.forecast_week_start}</td>
                    <td className="mono" style={{ textAlign: "right" }}>
                      {formatNumber(f.predicted_cash_in, lang)}
                    </td>
                    <td className="mono" style={{ textAlign: "right" }}>
                      {formatNumber(f.predicted_cash_out, lang)}
                    </td>
                    <td className="mono" style={{ textAlign: "right", color: "var(--muted)" }}>
                      {money(f.balance_p10)}
                    </td>
                    <td className="mono" style={{
                          textAlign: "right", fontWeight: 600,
                          color: f.predicted_balance < 0 ? "var(--flow-neg)" : undefined }}>
                      {money(f.predicted_balance)}
                    </td>
                    <td className="mono" style={{ textAlign: "right", color: "var(--muted)" }}>
                      {money(f.balance_p90)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Model qanday ishlaydi — auditga ochiq bo'lishi kerak */}
      <div className="section-head">
        <h2>{t("forecast.assumptionsTitle")}</h2>
      </div>
      <div className="card">
        <div className="card-body">
          <dl className="info-list">
            <dt>{t("forecast.method")}</dt>
            <dd>{t("forecast.methodValue")}</dd>
            <dt>{t("forecast.weekdayFactors")}</dt>
            <dd className="mono">
              {WEEKDAYS.map((w) => `${t(`forecast.wd.${w}`)} ${data.weekday_factors[w] ?? "1.000"}`)
                .join("  ·  ")}
            </dd>
            <dt>{t("forecast.uncertainty")}</dt>
            <dd>{t("forecast.uncertaintyValue")}</dd>
            <dt>{t("forecast.excluded")}</dt>
            <dd>{t("forecast.excludedValue")}</dd>
            {data.has_opening_balance && (
              <>
                <dt>{t("forecast.openingBalance")}</dt>
                <dd className="mono">{money(data.opening_balance)} {cur}</dd>
              </>
            )}
          </dl>
          <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 18, lineHeight: 1.65 }}>
            {t("forecast.disclaimer")}
          </p>
        </div>
      </div>
    </section>
  );
}
