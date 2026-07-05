/* 공통 상단 내비게이션 + 티커 테이프 + 유틸 — 모든 페이지에서 로드 */
(function () {
  var PAGES = [
    ["index.html", "섹터 대시보드"],
    ["megacap.html", "글로벌 메가캡"],
    ["perspective.html", "핵심 테제 트래킹"],
    ["worldflow.html", "세상 흐름 파악"],
    ["earnings.html", "미국 주요 실적 정리"],
    ["macro.html", "매크로 및 투자전략"],
  ];
  var here = location.pathname.split("/").pop() || "index.html";
  var nav = document.getElementById("topnav");
  if (nav) {
    var links = PAGES.map(function (p) {
      var act = p[0] === here ? " active" : "";
      return '<a class="navlink' + act + '" href="' + p[0] + '">' + p[1] + "</a>";
    }).join("");
    nav.innerHTML =
      '<div class="nav-inner"><span class="brand">FLOW<span class="dot">·</span>TRACKER</span>' +
      links + '</div><div id="tape"></div>';
  }

  /* 티커 테이프: 주요 벤치마크·섹터 등락을 흐르는 띠로 표시 */
  var TAPE_TICKERS = ["ACWI", "XLK", "SOXX", "XLF", "XLE", "ITA", "EWY", "229200.KS",
    "EWJ", "FXI", "GLD", "TLT", "URA", "BOTZ"];
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  fetch("data.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
    var tape = document.getElementById("tape");
    if (!tape || !d || !d.etfs) return;
    var items = TAPE_TICKERS.map(function (tk) { return d.etfs[tk]; }).filter(Boolean)
      .map(function (e) {
        var v = typeof e.r1d === "number" ? e.r1d : 0;
        var cls = v > 0 ? "up" : v < 0 ? "dn" : "flat";
        var ccy = /\.K[SQ]$/.test(e.ticker) ? "₩" : "$";
        var px = e.price >= 1000 ? Math.round(e.price).toLocaleString() : (+e.price).toFixed(2);
        return '<a class="tape-item" href="index.html">' +
          '<span class="t-nm">' + esc(e.name) + '</span>' +
          '<span class="t-px">' + ccy + px + '</span>' +
          '<span class="' + cls + '">' + (v > 0 ? "+" : "") + v.toFixed(2) + "%</span></a>";
      }).join("");
    if (!items) { tape.style.display = "none"; return; }
    /* 무한 스크롤: 동일 콘텐츠 2벌을 이어붙여 -50% 이동 루프 */
    tape.innerHTML = '<div class="tape-track">' + items + items + "</div>";
  }).catch(function () {
    var tape = document.getElementById("tape");
    if (tape) tape.style.display = "none";
  });
})();

/* 전역 헬퍼 */
function $q(sel, root) { return (root || document).querySelector(sel); }
function $qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
