(function () {
  "use strict";
  var S = window.PortfolioStore, state = S.load(), activeId = state.accounts[0].id;
  var COLORS = ["#6e9cff", "#ff7c8e", "#f0b429", "#58d3a6", "#b894ff", "#64b7ff", "#ff9d63", "#d5dfef"];
  function esc(v) { return String(v == null ? "" : v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
  function num(v, digits) { return Number(v || 0).toLocaleString("ko-KR", { maximumFractionDigits: digits == null ? 0 : digits }); }
  function krw(v) { return v == null ? "—" : "₩" + num(v); }
  function local(v, market) { return v == null ? "—" : (market === "US" ? "$" : "₩") + num(v, market === "US" ? 2 : 0); }
  function pct(v) { return v == null || !isFinite(v) ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2) + "%"; }
  function active() { return state.accounts.filter(function (a) { return a.id === activeId; })[0] || state.accounts[0]; }
  function allValue() { return S.aggregate(state, activeId).reduce(function (sum, h) { return sum + (h.valueKrw || 0); }, 0); }
  function renderTabs() {
    document.getElementById("account-tabs").innerHTML = state.accounts.map(function (a) {
      return '<button class="account-tab' + (a.id === activeId ? " on" : "") + '" data-account="' + esc(a.id) + '">' + esc(a.name) + '</button>';
    }).join("");
    document.querySelectorAll(".account-tab").forEach(function (b) { b.onclick = function () { activeId = b.dataset.account; render(); }; });
  }
  function ring(holdings, total) {
    if (!holdings.length || !total) return '<div class="allocation-ring"><svg viewBox="0 0 220 220"><circle class="ring-track" cx="110" cy="110" r="88"></circle></svg><div class="ring-center"><span class="label">보유 종목</span><b>0</b><small>매수 기록을 추가하세요</small></div></div>';
    var circumference = 2 * Math.PI * 88, offset = 0, paths = holdings.map(function (h, i) {
      var ratio = (h.valueKrw || 0) / total, length = Math.max(0, circumference * ratio - 4), item = '<circle class="ring-segment" cx="110" cy="110" r="88" stroke="' + COLORS[i % COLORS.length] + '" stroke-dasharray="' + length + ' ' + (circumference - length) + '" stroke-dashoffset="' + (-offset) + '"></circle>';
      offset += circumference * ratio; return item;
    }).join("");
    return '<div class="allocation-ring"><svg viewBox="0 0 220 220"><circle class="ring-track" cx="110" cy="110" r="88"></circle>' + paths + '</svg><div class="ring-center"><span class="label">총 평가액</span><b>' + krw(total) + '</b><small>' + holdings.length + '개 종목</small></div></div>';
  }
  function renderSummary() {
    var account = active(), holdings = S.aggregate(state, activeId), total = allValue(), cost = holdings.reduce(function (sum, h) { return sum + h.costKrw; }, 0), pnl = total - cost, rate = cost ? pnl / cost * 100 : null, fxLabel = state.fx && state.fx.price ? num(state.fx.price, 2) : "—";
    var list = holdings.map(function (h, i) { var weight = total ? (h.valueKrw || 0) / total * 100 : 0; return '<div class="allocation-item"><i class="dot" style="background:' + COLORS[i % COLORS.length] + '"></i><span class="name">' + esc(S.displayTicker(h.ticker)) + '</span><span class="weight">' + weight.toFixed(1) + '%</span></div>'; }).join("") || '<div class="allocation-item"><span></span><span class="name">아직 보유 종목이 없습니다.</span><span></span></div>';
    document.getElementById("portfolio-summary").innerHTML = '<div class="summary-grid">' + ring(holdings, total) + '<div class="summary-side"><div class="summary-title"><h3>' + esc(account.name) + '</h3><span>USD/KRW ' + fxLabel + '</span></div><div class="summary-metrics"><div class="metric"><span>총 매입금액</span><b>' + krw(cost) + '</b></div><div class="metric"><span>평가손익</span><b class="' + (pnl >= 0 ? "pos" : "neg") + '">' + krw(pnl) + '</b></div><div class="metric"><span>수익률</span><b class="' + (rate >= 0 ? "pos" : "neg") + '">' + pct(rate) + '</b></div></div><div class="allocation-list">' + list + '</div></div></div>';
  }
  function renderHoldings() {
    var holdings = S.aggregate(state, activeId), total = allValue();
    document.getElementById("holdings-body").innerHTML = holdings.length ? holdings.map(function (h) {
      var weight = total && h.valueKrw ? h.valueKrw / total * 100 : 0, cl = h.pnlKrw == null ? "" : h.pnlKrw >= 0 ? "pos" : "neg";
      return '<tr><td class="ticker">' + esc(S.displayTicker(h.ticker)) + '</td><td class="market">' + (h.market === "US" ? "미국" : "한국") + '</td><td>' + num(h.qty, 4) + '</td><td>' + local(h.avgLocal, h.market) + '</td><td>' + local(h.price, h.market) + '</td><td>' + krw(h.valueKrw) + '</td><td class="' + cl + '">' + krw(h.pnlKrw) + '<br><small>' + pct(h.returnPct) + '</small></td><td>' + weight.toFixed(1) + '%</td></tr>';
    }).join("") : '<tr><td colspan="8" class="empty-row">첫 매수 기록을 추가하면 보유 종목이 표시됩니다.</td></tr>';
  }
  function renderTransactions() {
    var recent = state.transactions.filter(function (t) { return t.accountId === activeId; }).slice().sort(function (a,b) { return String(b.date).localeCompare(String(a.date)) || String(b.createdAt).localeCompare(String(a.createdAt)); }).slice(0,8);
    document.getElementById("recent-transactions").innerHTML = recent.length ? recent.map(function (t) { return '<div class="tx-row"><span class="date">' + esc(t.date) + '</span><span class="market">' + (t.market === "US" ? "미국" : "한국") + '</span><b>' + esc(S.displayTicker(t.ticker)) + '</b><span class="' + (t.side === "buy" ? "buy" : "sell") + '">' + (t.side === "buy" ? "매수" : "매도") + '</span><span class="tx-price">' + num(t.qty,4) + '주 · ' + local(t.price,t.market) + '</span><button class="icon-btn" data-delete-tx="' + esc(t.id) + '" aria-label="기록 삭제">×</button></div>'; }).join("") : '<div class="empty-row">아직 매매 기록이 없습니다.</div>';
    document.querySelectorAll("[data-delete-tx]").forEach(function (b) { b.onclick = function () { if (!confirm("이 매매 기록을 삭제할까요?")) return; state.transactions = state.transactions.filter(function (t) { return t.id !== b.dataset.deleteTx; }); S.save(state); render(); }; });
  }
  function renderLists() {
    var buys = state.buyList.slice().sort(function (a,b) { return String(b.createdAt).localeCompare(String(a.createdAt)); });
    document.getElementById("buy-list").innerHTML = buys.length ? buys.map(function (x) { return '<div class="buy-row"><b class="buy-ticker">' + esc(x.ticker) + '</b><span class="reason">' + esc(x.reason) + '</span><button class="icon-btn" data-delete-buy="' + esc(x.id) + '" aria-label="바잉리스트 삭제">×</button></div>'; }).join("") : '<div class="empty-row">종목과 매수 이유를 추가해 주세요.</div>';
    document.getElementById("watch-list").innerHTML = state.watchlist.length ? state.watchlist.map(function (x) { var quote = state.prices[S.groupKey(x.market, x.ticker)], price = quote && quote.price; return '<div class="watch-row"><div><b class="watch-ticker">' + esc(S.displayTicker(x.ticker)) + '</b><span class="watch-meta"> · ' + (x.market === "US" ? "미국" : "한국") + '</span></div><span class="watch-price">' + local(price, x.market) + '</span><button class="icon-btn" data-delete-watch="' + esc(x.id) + '" aria-label="관심종목 삭제">×</button></div>'; }).join("") : '<div class="empty-row">관심 종목을 추가해 주세요.</div>';
    document.querySelectorAll("[data-delete-buy]").forEach(function (b) { b.onclick = function () { state.buyList = state.buyList.filter(function (x) { return x.id !== b.dataset.deleteBuy; }); S.save(state); renderLists(); }; });
    document.querySelectorAll("[data-delete-watch]").forEach(function (b) { b.onclick = function () { state.watchlist = state.watchlist.filter(function (x) { return x.id !== b.dataset.deleteWatch; }); S.save(state); renderLists(); }; });
  }
  function render() { renderTabs(); renderSummary(); renderHoldings(); renderTransactions(); renderLists(); }
  function setUpdated(text) { document.getElementById("portfolio-updated").textContent = text; }
  function wire() {
    var form = document.getElementById("transaction-form"); form.date.value = new Date().toISOString().slice(0,10); form.fx.value = state.fx && state.fx.price ? Number(state.fx.price).toFixed(2) : "";
    form.addEventListener("submit", function (e) { e.preventDefault(); var fd = new FormData(form), market = fd.get("market"), ticker = S.tickerFor(fd.get("ticker"),market), qty = Number(fd.get("qty")), price = Number(fd.get("price")); if (!ticker || !(qty>0) || !(price>0)) return; state.transactions.push({ id:S.id("tx"), accountId:activeId, date:fd.get("date"), market:market, ticker:ticker, side:fd.get("side"), qty:qty, price:price, fx:Number(fd.get("fx")) || Number(state.fx && state.fx.price) || 1350, createdAt:new Date().toISOString() }); S.save(state); form.reset(); form.date.value = new Date().toISOString().slice(0,10); form.fx.value = state.fx && state.fx.price ? Number(state.fx.price).toFixed(2) : ""; render(); refresh(); });
    document.getElementById("add-account").onclick = function () { var name = prompt("새 포트폴리오 이름", "포트폴리오 " + (state.accounts.length + 1)); if (!name || !name.trim()) return; var a={id:S.id("account"),name:name.trim()}; state.accounts.push(a); activeId=a.id; S.save(state); render(); };
    document.getElementById("rename-account").onclick = function () { var a=active(), name=prompt("포트폴리오 이름",a.name); if(!name||!name.trim())return;a.name=name.trim();S.save(state);render(); };
    document.getElementById("delete-account").onclick = function () { if(state.accounts.length<=1){alert("포트폴리오는 하나 이상 남겨야 합니다.");return;}var a=active();if(!confirm(a.name+"과 해당 매매 기록을 삭제할까요?"))return;state.accounts=state.accounts.filter(function(x){return x.id!==a.id;});state.transactions=state.transactions.filter(function(x){return x.accountId!==a.id;});activeId=state.accounts[0].id;S.save(state);render(); };
    document.getElementById("buy-form").addEventListener("submit",function(e){e.preventDefault();var f=new FormData(e.currentTarget),ticker=String(f.get("ticker")||"").trim().toUpperCase(),reason=String(f.get("reason")||"").trim();if(!ticker||!reason)return;state.buyList.push({id:S.id("buy"),ticker:ticker,reason:reason,createdAt:new Date().toISOString()});S.save(state);e.currentTarget.reset();renderLists();});
    document.getElementById("watch-form").addEventListener("submit",function(e){e.preventDefault();var f=new FormData(e.currentTarget),market=f.get("market"),ticker=S.tickerFor(f.get("ticker"),market);if(!ticker)return;if(state.watchlist.some(function(x){return S.groupKey(x.market,x.ticker)===S.groupKey(market,ticker);})){return;}state.watchlist.push({id:S.id("watch"),market:market,ticker:ticker,createdAt:new Date().toISOString()});S.save(state);e.currentTarget.reset();renderLists();refresh();});
  }
  async function refresh() { setUpdated("시세 갱신 중…"); try { state = await S.refresh(state); setUpdated("시세 갱신 " + new Date().toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit"})); } catch(e) { setUpdated("마지막 저장 시세 표시"); } render(); }
  wire(); render(); refresh();
})();
