/* 개인 포트폴리오 데이터: 이 브라우저의 localStorage에만 저장 */
(function () {
  "use strict";
  var KEY = "vantage-portfolio-v1";
  var DEFAULT = {
    accounts: [{ id: "portfolio-1", name: "포트폴리오 1", cashKrw: 0, cashUsd: 0 }, { id: "portfolio-2", name: "포트폴리오 2", cashKrw: 0, cashUsd: 0 }],
    transactions: [], buyList: [], watchlist: [], prices: {}, fx: null
  };
  function id(prefix) { return prefix + "-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
  function load() {
    try {
      var parsed = JSON.parse(localStorage.getItem(KEY) || "null");
      if (!parsed) return JSON.parse(JSON.stringify(DEFAULT));
      return {
        accounts: Array.isArray(parsed.accounts) && parsed.accounts.length ? parsed.accounts : JSON.parse(JSON.stringify(DEFAULT.accounts)),
        transactions: Array.isArray(parsed.transactions) ? parsed.transactions : [],
        buyList: Array.isArray(parsed.buyList) ? parsed.buyList : [],
        watchlist: Array.isArray(parsed.watchlist) ? parsed.watchlist : [],
        prices: parsed.prices || {}, fx: parsed.fx || null
      };
    } catch (e) { return JSON.parse(JSON.stringify(DEFAULT)); }
  }
  function save(data) { localStorage.setItem(KEY, JSON.stringify(data)); return data; }
  function tickerFor(ticker, market) {
    ticker = String(ticker || "").trim().toUpperCase();
    if (market === "KR" && !/\.(KS|KQ)$/.test(ticker)) return ticker + ".KS";
    return ticker;
  }
  function displayTicker(ticker) { return String(ticker || "").replace(/\.(KS|KQ)$/i, ""); }
  function groupKey(market, ticker) { return market + ":" + tickerFor(ticker, market); }
  function aggregate(data, accountId) {
    var result = {};
    data.transactions.filter(function (t) { return t.accountId === accountId; }).slice().sort(function (a, b) {
      return String(a.date).localeCompare(String(b.date)) || String(a.createdAt || "").localeCompare(String(b.createdAt || ""));
    }).forEach(function (t) {
      var market = t.market === "KR" ? "KR" : "US", ticker = tickerFor(t.ticker, market), key = groupKey(market, ticker);
      var h = result[key] || (result[key] = { key: key, market: market, ticker: ticker, qty: 0, costLocal: 0, costKrw: 0, realizedKrw: 0 });
      var qty = Number(t.qty) || 0, price = Number(t.price) || 0, fx = Number(t.fx) || Number(data.fx && data.fx.price) || 1350;
      if (t.side === "sell") {
        var sold = Math.min(qty, h.qty), avgLocal = h.qty ? h.costLocal / h.qty : 0, avgKrw = h.qty ? h.costKrw / h.qty : 0;
        h.realizedKrw += sold * (price * (market === "US" ? fx : 1) - avgKrw);
        h.qty -= sold; h.costLocal -= sold * avgLocal; h.costKrw -= sold * avgKrw;
      } else {
        h.qty += qty; h.costLocal += qty * price; h.costKrw += qty * price * (market === "US" ? fx : 1);
      }
    });
    return Object.keys(result).map(function (key) {
      var h = result[key]; if (h.qty <= 0.0000001) return null;
      var q = h.qty, quote = data.prices[h.key], current = quote && Number(quote.price);
      h.avgLocal = q ? h.costLocal / q : 0; h.avgKrw = q ? h.costKrw / q : 0;
      h.price = isFinite(current) ? current : null; h.fx = Number(data.fx && data.fx.price) || 1350;
      h.valueKrw = h.price == null ? null : h.price * q * (h.market === "US" ? h.fx : 1);
      h.pnlKrw = h.valueKrw == null ? null : h.valueKrw - h.costKrw;
      h.returnPct = h.pnlKrw == null || !h.costKrw ? null : h.pnlKrw / h.costKrw * 100;
      h.updated = quote && quote.updated; return h;
    }).filter(Boolean).sort(function (a, b) { return (b.valueKrw || 0) - (a.valueKrw || 0); });
  }
  async function priceOne(market, ticker) {
    var symbol = tickerFor(ticker, market), source = "http://query1.finance.yahoo.com/v8/finance/chart/" + encodeURIComponent(symbol) + "?range=5d%26interval=1d";
    /* Yahoo는 브라우저 CORS를 허용하지 않아 읽기 전용 중계로 응답만 가져온다. 요청에는 티커만 포함된다. */
    var response = await fetch("https://r.jina.ai/" + source, { cache: "no-store" }); if (!response.ok) throw new Error("quote unavailable");
    var text = await response.text(), start = text.indexOf('{"chart"'); if (start < 0) throw new Error("quote unavailable");
    var json = JSON.parse(text.slice(start)), res = json && json.chart && json.chart.result && json.chart.result[0];
    var quote = res && res.meta && (res.meta.regularMarketPrice || res.meta.previousClose);
    if (!isFinite(Number(quote))) throw new Error("invalid quote");
    return { price: Number(quote), currency: res.meta.currency || (market === "KR" ? "KRW" : "USD"), updated: new Date().toISOString() };
  }
  async function fxUsdKrw() {
    var response = await fetch("https://api.frankfurter.app/latest?from=USD&to=KRW", { cache: "no-store" }); if (!response.ok) throw new Error("fx unavailable");
    var json = await response.json(), quote = json && json.rates && json.rates.KRW;
    if (!isFinite(Number(quote))) throw new Error("invalid fx");
    return { price: Number(quote), currency: "KRW", updated: new Date().toISOString() };
  }
  async function refresh(data) {
    var symbols = {}, i;
    data.accounts.forEach(function (a) { aggregate(data, a.id).forEach(function (h) { symbols[h.key] = { market: h.market, ticker: h.ticker }; }); });
    data.watchlist.forEach(function (w) { symbols[groupKey(w.market, w.ticker)] = { market: w.market, ticker: tickerFor(w.ticker, w.market) }; });
    var keys = Object.keys(symbols);
    await Promise.all(keys.map(async function (key) {
      try { data.prices[key] = await priceOne(symbols[key].market, symbols[key].ticker); } catch (e) {}
    }));
    try { data.fx = await fxUsdKrw(); } catch (e) {}
    save(data); return data;
  }
  window.PortfolioStore = { load: load, save: save, id: id, aggregate: aggregate, refresh: refresh, tickerFor: tickerFor, displayTicker: displayTicker, groupKey: groupKey };
})();
