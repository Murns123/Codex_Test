import { getPortfolio, recentTrades } from "@/lib/db";
import { tradingConfig } from "@/lib/config";

export const dynamic = "force-dynamic";

const money = (n: number) => new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD" }).format(n);
const pct = (n: number) => `${(n * 100).toFixed(2)}%`;

export default async function Home() {
  const portfolio = await getPortfolio();
  const trades = await recentTrades(20);

  return (
    <main>
      <div className="row">
        <div>
          <h1>JEV × EODHD Paper Trader</h1>
          <p>15-minute market research engine for ASX and US equities.</p>
        </div>
        <div className="status">
          <span className="dot" />
          {tradingConfig.paperTradingEnabled ? "Paper execution enabled" : "Analysis-only mode"}
        </div>
      </div>

      <section className="grid">
        <div className="card"><div className="muted">Portfolio value</div><div className="metric">{money(portfolio.totalValueAud)}</div></div>
        <div className="card"><div className="muted">Cash</div><div className="metric">{money(portfolio.cashAud)}</div></div>
        <div className="card"><div className="muted">Holdings</div><div className="metric">{money(portfolio.holdingsAud)}</div></div>
        <div className="card"><div className="muted">Return</div><div className={`metric ${portfolio.totalReturnAud >= 0 ? "good" : "bad"}`}>{money(portfolio.totalReturnAud)} <span style={{fontSize:14}}>{pct(portfolio.totalReturnPct)}</span></div></div>
      </section>

      <section className="card">
        <div className="row">
          <h2>Open positions</h2>
          <span className="muted">{portfolio.positions.length}/{tradingConfig.maxPositions} positions</span>
        </div>
        <table>
          <thead><tr><th>Symbol</th><th>Market</th><th>Qty</th><th>Avg price</th><th>Last price</th><th>Value AUD</th></tr></thead>
          <tbody>
            {portfolio.positions.length === 0 ? (
              <tr><td colSpan={6} className="muted">No paper positions yet.</td></tr>
            ) : portfolio.positions.map((p) => (
              <tr key={p.symbol}>
                <td className="code">{p.symbol}</td><td>{p.market}</td><td>{p.quantity}</td>
                <td>{p.avgPriceNative.toFixed(2)}</td><td>{p.lastPriceNative.toFixed(2)}</td>
                <td>{money(p.quantity * p.lastPriceNative * p.lastFxToAud)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <div className="row"><h2>Recent trades</h2><span className="muted">NABtrade-style costs + configurable slippage/FX</span></div>
        <table>
          <thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Brokerage</th><th>Net AUD</th><th>Reason</th></tr></thead>
          <tbody>
            {trades.length === 0 ? (
              <tr><td colSpan={8} className="muted">No trades recorded yet.</td></tr>
            ) : trades.map((t: any) => (
              <tr key={t.id}>
                <td>{new Date(t.created_at).toLocaleString("en-AU", { timeZone: "Australia/Melbourne" })}</td>
                <td className="code">{t.symbol}</td><td>{t.side}</td><td>{Number(t.quantity)}</td>
                <td>{Number(t.price_native).toFixed(2)}</td><td>{money(Number(t.brokerage_aud))}</td>
                <td>{money(Number(t.net_aud))}</td><td>{t.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Configuration</h2>
        <p className="code">
          max positions={tradingConfig.maxPositions} · max position={pct(tradingConfig.maxPositionPct)} ·
          JEV buy threshold={pct(tradingConfig.entryConfidence)} · stop loss={pct(tradingConfig.stopLossPct)} ·
          take profit={pct(tradingConfig.takeProfitPct)}
        </p>
      </section>
    </main>
  );
}
