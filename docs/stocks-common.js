/* 공통 렌더 유틸 — 포맷터 / 스파크라인 / 라인차트 / 캔들차트 / 경량 마크다운 / 모달 */

/* ---------- 데이터 로드 ---------- */
function fetchJSON(path) {
  return fetch(path + "?v=" + Date.now()).then(function (r) {
    if (!r.ok) throw new Error(path + " HTTP " + r.status);
    return r.json();
  });
}

/* ---------- 포맷터 ---------- */
function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function num(v) { return typeof v === "number" && isFinite(v) ? v : 0; }
function pctClass(v) { v = num(v); return v > 0 ? "up" : v < 0 ? "dn" : "flat"; }
function fmtPct(v, digits) {
  v = num(v);
  var d = digits == null ? 2 : digits;
  return (v > 0 ? "+" : "") + v.toFixed(d) + "%";
}
function pctSpan(v, digits) {
  return '<span class="' + pctClass(v) + '">' + fmtPct(v, digits) + "</span>";
}
function fmtPrice(v, ccy) {
  v = num(v);
  var s = v >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
                    : v.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return (ccy || "$") + s;
}
function fmtMcap(usd) {
  usd = num(usd);
  if (usd >= 1e12) return "$" + (usd / 1e12).toFixed(2) + "T";
  if (usd >= 1e9) return "$" + (usd / 1e9).toFixed(0) + "B";
  return "$" + (usd / 1e6).toFixed(0) + "M";
}
/* 수익률 → 히트맵 배경색 (한국식: 상승 빨강 / 하락 파랑) */
function heatBg(v, cap) {
  v = num(v); cap = cap || 6;
  var a = Math.min(Math.abs(v) / cap, 1) * 0.55;
  if (v > 0) return "rgba(240,71,90," + a.toFixed(3) + ")";
  if (v < 0) return "rgba(61,126,255," + a.toFixed(3) + ")";
  return "transparent";
}
function daysAgo(dateStr) {
  if (!dateStr) return 9999;
  var d = new Date(dateStr + "T00:00:00");
  return Math.floor((Date.now() - d.getTime()) / 86400000);
}

/* ---------- SVG 차트 ---------- */
function sparklineSVG(vals, w, h, cls) {
  vals = (vals || []).map(num);
  w = w || 90; h = h || 26;
  if (vals.length < 2) return '<svg width="' + w + '" height="' + h + '"></svg>';
  var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals);
  var rng = mx - mn || 1;
  var pts = vals.map(function (v, i) {
    var x = (i / (vals.length - 1)) * (w - 2) + 1;
    var y = h - 2 - ((v - mn) / rng) * (h - 4);
    return x.toFixed(1) + "," + y.toFixed(1);
  }).join(" ");
  var last = vals[vals.length - 1];
  var color = last > vals[0] ? "var(--up)" : last < vals[0] ? "var(--dn)" : "var(--muted)";
  return '<svg class="' + (cls || "") + '" width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + " " + h + '">' +
    '<polyline fill="none" stroke="' + color + '" stroke-width="1.5" points="' + pts + '"/></svg>';
}

/* 멀티 라인차트: series=[{name, values(누적%), color}] */
function lineChartSVG(series, w, h) {
  w = w || 900; h = h || 300;
  var padL = 44, padR = 10, padT = 12, padB = 20;
  var all = [];
  series.forEach(function (s) { all = all.concat(s.values.map(num)); });
  if (!all.length) return '<div class="empty">데이터 없음</div>';
  var mn = Math.min.apply(null, all), mx = Math.max.apply(null, all);
  if (mn === mx) { mn -= 1; mx += 1; }
  var span = mx - mn;
  mn -= span * 0.05; mx += span * 0.05; span = mx - mn;
  function y(v) { return padT + (1 - (v - mn) / span) * (h - padT - padB); }
  var maxLen = Math.max.apply(null, series.map(function (s) { return s.values.length; }));
  function x(i, len) { return padL + (i / Math.max(len - 1, 1)) * (w - padL - padR); }

  var gl = "";
  var steps = 5;
  for (var g = 0; g <= steps; g++) {
    var gv = mn + (span * g) / steps;
    var gy = y(gv);
    gl += '<line x1="' + padL + '" y1="' + gy + '" x2="' + (w - padR) + '" y2="' + gy +
      '" stroke="var(--border)" stroke-width="1"/>' +
      '<text x="' + (padL - 6) + '" y="' + (gy + 4) + '" fill="var(--muted)" font-size="10" text-anchor="end">' +
      gv.toFixed(1) + "%</text>";
  }
  if (mn < 0 && mx > 0) {
    gl += '<line x1="' + padL + '" y1="' + y(0) + '" x2="' + (w - padR) + '" y2="' + y(0) +
      '" stroke="var(--muted)" stroke-width="1" stroke-dasharray="3,3"/>';
  }
  var lines = series.map(function (s, i) {
    var pts = s.values.map(function (v, j) {
      return x(j, s.values.length).toFixed(1) + "," + y(num(v)).toFixed(1);
    }).join(" ");
    var title = '<title>' + escapeHtml(s.name) + "</title>";
    /* 굵은 투명 히트박스(호버 인식용) + 실제 표시선(pointer-events 없음, 겹침 방지) */
    return '<polyline class="tl-hit" data-idx="' + i + '" fill="none" stroke="transparent" stroke-width="12" ' +
      'style="cursor:pointer" points="' + pts + '">' + title + "</polyline>" +
      '<polyline class="tl-line" data-idx="' + i + '" fill="none" stroke="' + s.color +
      '" stroke-width="1.8" points="' + pts + '" style="pointer-events:none;transition:opacity .12s,stroke-width .12s">' +
      title + "</polyline>";
  }).join("");
  return '<svg width="100%" viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none" style="min-width:640px">' +
    gl + lines + "</svg>";
}

/* 라인차트 호버 하이라이트: root 안의 .tl-hit(히트박스)에 마우스 올리면 해당 data-idx 선만
   진하게, 나머지는 흐리게. root 안에 [data-line-idx] 요소(범례 등)가 있으면 서로 연동. */
function wireLineHover(root) {
  var hits = $qa(".tl-hit", root);
  if (!hits.length) return;
  function setActive(idx) {
    $qa(".tl-line", root).forEach(function (el) {
      var on = idx === null || el.dataset.idx === String(idx);
      el.style.opacity = on ? "1" : "0.15";
      el.style.strokeWidth = (idx !== null && on) ? "3" : "1.8";
    });
    $qa("[data-line-idx]", root).forEach(function (el) {
      el.classList.toggle("hl-active", idx !== null && el.dataset.lineIdx === String(idx));
      el.style.opacity = (idx === null || el.dataset.lineIdx === String(idx)) ? "1" : "0.4";
    });
  }
  hits.forEach(function (hit) {
    hit.addEventListener("mouseenter", function () { setActive(hit.dataset.idx); });
    hit.addEventListener("mouseleave", function () { setActive(null); });
  });
  $qa("[data-line-idx]", root).forEach(function (el) {
    el.addEventListener("mouseenter", function () { setActive(el.dataset.lineIdx); });
    el.addEventListener("mouseleave", function () { setActive(null); });
  });
}

/* 일봉 캔들차트 + 거래량 */
function candleChartSVG(candles, w, h) {
  candles = candles || [];
  w = w || 820; h = h || 320;
  if (candles.length < 2) return '<div class="empty">캔들 데이터 없음</div>';
  var padL = 52, padR = 8, padT = 10;
  var volH = 54, gap = 8, padB = 20;
  var priceH = h - volH - gap - padT - padB;
  var hi = Math.max.apply(null, candles.map(function (c) { return c.h; }));
  var lo = Math.min.apply(null, candles.map(function (c) { return c.l; }));
  var span = hi - lo || 1;
  hi += span * 0.03; lo -= span * 0.03; span = hi - lo;
  var maxV = Math.max.apply(null, candles.map(function (c) { return c.v; })) || 1;
  var n = candles.length;
  var cw = (w - padL - padR) / n;
  var bw = Math.max(Math.min(cw * 0.65, 12), 1.5);
  function yP(v) { return padT + (1 - (v - lo) / span) * priceH; }

  var gl = "";
  for (var g = 0; g <= 4; g++) {
    var gv = lo + (span * g) / 4, gy = yP(gv);
    gl += '<line x1="' + padL + '" y1="' + gy + '" x2="' + (w - padR) + '" y2="' + gy + '" stroke="var(--border)"/>' +
      '<text x="' + (padL - 6) + '" y="' + (gy + 4) + '" fill="var(--muted)" font-size="10" text-anchor="end">' +
      (gv >= 1000 ? Math.round(gv).toLocaleString() : gv.toFixed(2)) + "</text>";
  }
  var body = candles.map(function (c, i) {
    var cx = padL + cw * i + cw / 2;
    var up = c.c >= c.o;
    var col = up ? "var(--up)" : "var(--dn)";
    var oT = yP(Math.max(c.o, c.c)), oB = yP(Math.min(c.o, c.c));
    var bh = Math.max(oB - oT, 1);
    var vy = padT + priceH + gap;
    var vh = (c.v / maxV) * volH;
    var lbl = "";
    if (i % Math.ceil(n / 6) === 0) {
      lbl = '<text x="' + cx + '" y="' + (h - 5) + '" fill="var(--muted)" font-size="10" text-anchor="middle">' +
        c.d.slice(5) + "</text>";
    }
    return '<line x1="' + cx + '" y1="' + yP(c.h) + '" x2="' + cx + '" y2="' + yP(c.l) + '" stroke="' + col + '" stroke-width="1"/>' +
      '<rect x="' + (cx - bw / 2) + '" y="' + oT + '" width="' + bw + '" height="' + bh + '" fill="' + col + '"><title>' +
      c.d + "  시 " + c.o + " 고 " + c.h + " 저 " + c.l + " 종 " + c.c + "</title></rect>" +
      '<rect x="' + (cx - bw / 2) + '" y="' + (vy + volH - vh) + '" width="' + bw + '" height="' + Math.max(vh, 0.5) +
      '" fill="' + col + '" opacity="0.45"/>' + lbl;
  }).join("");
  return '<div style="overflow-x:auto"><svg width="100%" viewBox="0 0 ' + w + " " + h +
    '" preserveAspectRatio="none" style="min-width:640px">' + gl + body + "</svg></div>";
}

/* ---------- 경량 마크다운 렌더 (헤딩/굵게/기울임/리스트/링크/코드/문단) ---------- */
function mdRender(src) {
  if (!src) return "";
  var lines = String(src).split(/\r?\n/);
  var out = [], inList = false;
  function inline(s) {
    s = escapeHtml(s);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s;
  }
  lines.forEach(function (ln) {
    var m;
    if ((m = ln.match(/^(#{1,3})\s+(.*)/))) {
      if (inList) { out.push("</ul>"); inList = false; }
      var lv = m[1].length;
      out.push("<h" + lv + ">" + inline(m[2]) + "</h" + lv + ">");
    } else if ((m = ln.match(/^\s*[-*]\s+(.*)/))) {
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push("<li>" + inline(m[1]) + "</li>");
    } else if (ln.trim() === "") {
      if (inList) { out.push("</ul>"); inList = false; }
    } else {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push("<p>" + inline(ln) + "</p>");
    }
  });
  if (inList) out.push("</ul>");
  return '<div class="md">' + out.join("") + "</div>";
}

/* ---------- 모달 ---------- */
function openModal(titleHtml, bodyHtml, headerExtraHtml) {
  closeModal();
  var back = document.createElement("div");
  back.className = "modal-back";
  back.id = "modal-back";
  back.innerHTML =
    '<div class="modal"><div class="m-head"><h3>' + titleHtml + "</h3>" + (headerExtraHtml || "") +
    '<button class="m-close" onclick="closeModal()">닫기 ✕</button></div>' +
    '<div class="m-body">' + bodyHtml + "</div></div>";
  back.addEventListener("click", function (e) { if (e.target === back) closeModal(); });
  document.body.appendChild(back);
  document.body.style.overflow = "hidden";
}
function closeModal() {
  var b = document.getElementById("modal-back");
  if (b) b.remove();
  document.body.style.overflow = "";
}
document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeModal(); });

/* ---------- 테이블 정렬 ---------- */
function makeSortable(table, rows, renderRows) {
  /* rows: 원본 배열, renderRows(sortedRows) 재렌더 콜백.
     th에 data-key(정렬 필드), data-str("1"이면 문자열 정렬) 지정 */
  var state = { key: null, dir: -1 };
  $qa("thead th[data-key]", table).forEach(function (th) {
    th.addEventListener("click", function () {
      var k = th.dataset.key;
      state.dir = state.key === k ? -state.dir : -1;
      state.key = k;
      var isStr = th.dataset.str === "1";
      var sorted = rows.slice().sort(function (a, b) {
        var av = a[k], bv = b[k];
        if (isStr) return String(av).localeCompare(String(bv)) * state.dir;
        return (num(av) - num(bv)) * state.dir;
      });
      renderRows(sorted);
    });
  });
}

/* ================= 기술적 분석 (megacap.json 캔들에서 클라이언트 계산) =================
   재승씨식 거래량+이동평균선 중심 + 대중이 많이 보는 순서(이평선→거래량→지지·이격→RSI→MACD→
   볼린저→일목→삼각수렴·돌파)로 각 지표를 0~100 점으로 환산해 가중합(technical score).
   캔들은 최근 ~380일이 일봉, 그 이전은 주봉으로 섞여 있어 '일봉 구간'만 잘라 계산한다. */
function _sma(arr, p, endIdx) {
  if (endIdx == null) endIdx = arr.length - 1;
  if (endIdx - p + 1 < 0) return null;
  var s = 0;
  for (var i = endIdx - p + 1; i <= endIdx; i++) s += arr[i];
  return s / p;
}
function _emaSeries(arr, p) {
  if (!arr.length) return [];
  var k = 2 / (p + 1), out = [arr[0]];
  for (var i = 1; i < arr.length; i++) out.push(arr[i] * k + out[i - 1] * (1 - k));
  return out;
}
function _rsi(closes, p) {
  if (closes.length < p + 1) return null;
  var gain = 0, loss = 0;
  for (var i = closes.length - p; i < closes.length; i++) {
    var ch = closes[i] - closes[i - 1];
    if (ch >= 0) gain += ch; else loss -= ch;
  }
  if (loss === 0) return 100;
  var rs = (gain / p) / (loss / p);
  return 100 - 100 / (1 + rs);
}
/* 최근 ~400일(일봉 구간)만 반환 */
function _dailyTail(candles) {
  if (!candles || !candles.length) return [];
  var last = new Date(candles[candles.length - 1].d).getTime();
  var cut = last - 400 * 86400000;
  return candles.filter(function (c) { return new Date(c.d).getTime() >= cut; });
}
function _clamp(v) { return v < 0 ? 0 : v > 100 ? 100 : v; }

function computeTA(candles) {
  var d = _dailyTail(candles);
  if (d.length < 30) return null;
  var closes = d.map(function (c) { return c.c; });
  var highs = d.map(function (c) { return c.h; });
  var lows = d.map(function (c) { return c.l; });
  var vols = d.map(function (c) { return c.v || 0; });
  var n = closes.length, px = closes[n - 1];
  var ma5 = _sma(closes, 5), ma20 = _sma(closes, 20), ma60 = _sma(closes, 60), ma120 = _sma(closes, 120);
  var subs = [];

  // 1) 이동평균선 정배열 (가장 대중적) — MA5>20>60>120 + 종가>MA20
  (function () {
    var ok = 0, tot = 0;
    if (ma5 != null && ma20 != null) { tot++; if (ma5 > ma20) ok++; }
    if (ma20 != null && ma60 != null) { tot++; if (ma20 > ma60) ok++; }
    if (ma60 != null && ma120 != null) { tot++; if (ma60 > ma120) ok++; }
    var align = tot ? (ok / tot) * 85 : 42;
    if (ma20 != null && px > ma20) align += 15;
    var detail = ma5 != null && ma20 != null && ma60 != null
      ? (ok === tot && tot === 3 ? "완전 정배열" : ok >= 2 ? "부분 정배열" : "역배열 성격")
      : "데이터 부족";
    subs.push({ key: "ma", label: "이동평균선 정배열", score: _clamp(align), detail: detail, weight: 24 });
  })();

  // 2) 거래량 — 최근 5일 평균 / 그 이전 20일 평균 (재승씨: 거래량 동반)
  (function () {
    var v5 = _sma(vols, 5), v20 = _sma(vols, 20, n - 6);
    if (!v5 || !v20) { subs.push({ key: "vol", label: "거래량", score: 50, detail: "데이터 부족", weight: 18 }); return; }
    var ratio = v5 / v20;
    // 상승과 동반된 거래량 증가에 가점 (최근 5일 수익률 부호 반영)
    var r5 = closes[n - 6] ? (px / closes[n - 6] - 1) : 0;
    var sc = _clamp(40 + (ratio - 1) * 50 + (r5 > 0 ? 10 : -10));
    subs.push({ key: "vol", label: "거래량", score: sc, detail: "5일/20일 " + ratio.toFixed(2) + "배" + (r5 > 0 ? " · 상승 동반" : ""), weight: 18 });
  })();

  // 3) 이평선 지지·이격도 — 상승 MA20 위 0~7% = 이상적 눌림목 지지
  (function () {
    if (ma20 == null) { subs.push({ key: "sup", label: "이평선 지지·이격도", score: 50, detail: "-", weight: 14 }); return; }
    var gap = (px / ma20 - 1) * 100;
    var rising = ma5 != null && ma20 != null && ma5 > ma20;
    var sc;
    if (gap < -8) sc = 25;                       // 20일선 크게 이탈
    else if (gap < 0) sc = 55 + gap * 2;         // 살짝 아래
    else if (gap <= 7) sc = 100 - gap * 2;       // 이상적 지지 구간
    else sc = _clamp(86 - (gap - 7) * 3);        // 과열(이격 과다)
    if (rising) sc += 6;
    subs.push({ key: "sup", label: "이평선 지지·이격도", score: _clamp(sc), detail: "20일선 대비 " + (gap >= 0 ? "+" : "") + gap.toFixed(1) + "%", weight: 14 });
  })();

  // 4) RSI(14) — 50~65 건강한 상승, 70+ 과열, 30- 침체
  (function () {
    var r = _rsi(closes, 14);
    if (r == null) { subs.push({ key: "rsi", label: "RSI(14)", score: 50, detail: "-", weight: 10 }); return; }
    var sc;
    if (r >= 50 && r <= 65) sc = 100;
    else if (r > 65) sc = _clamp(100 - (r - 65) * 3);   // 과열 감점
    else if (r >= 40) sc = 60 + (r - 40) * 4;
    else sc = _clamp(r * 1.2);                            // 침체
    subs.push({ key: "rsi", label: "RSI(14)", score: _clamp(sc), detail: r.toFixed(0) + (r > 70 ? " (과열)" : r < 30 ? " (침체)" : ""), weight: 10 });
  })();

  // 5) MACD(12,26,9) — MACD>Signal & MACD>0 강세
  (function () {
    if (n < 35) { subs.push({ key: "macd", label: "MACD", score: 50, detail: "-", weight: 10 }); return; }
    var e12 = _emaSeries(closes, 12), e26 = _emaSeries(closes, 26);
    var macdLine = closes.map(function (_, i) { return e12[i] - e26[i]; });
    var sig = _emaSeries(macdLine, 9);
    var m = macdLine[n - 1], s = sig[n - 1];
    var sc = 50 + (m > s ? 25 : -20) + (m > 0 ? 20 : -15);
    subs.push({ key: "macd", label: "MACD", score: _clamp(sc), detail: (m > s ? "골든크로스 상태" : "데드크로스 상태") + (m > 0 ? " · 0선 위" : " · 0선 아래"), weight: 10 });
  })();

  // 6) 볼린저밴드 %B (20,2)
  (function () {
    if (n < 20) { subs.push({ key: "boll", label: "볼린저밴드", score: 50, detail: "-", weight: 6 }); return; }
    var mid = _sma(closes, 20), sd = 0;
    for (var i = n - 20; i < n; i++) sd += Math.pow(closes[i] - mid, 2);
    sd = Math.sqrt(sd / 20);
    var up = mid + 2 * sd, lo = mid - 2 * sd;
    var pctB = up === lo ? 0.5 : (px - lo) / (up - lo);
    var sc = pctB >= 0.5 && pctB <= 0.9 ? 100 : pctB > 0.9 ? _clamp(100 - (pctB - 0.9) * 200) : _clamp(pctB * 120);
    subs.push({ key: "boll", label: "볼린저밴드 %B", score: _clamp(sc), detail: "%B " + pctB.toFixed(2) + (pctB > 1 ? " (상단 돌파)" : ""), weight: 6 });
  })();

  // 7) 일목균형표 구름대 — 종가 vs 선행스팬A/B (라라리엔 참고: 구름대 지지)
  (function () {
    if (n < 52) { subs.push({ key: "ichi", label: "일목균형표 구름대", score: 50, detail: "데이터 부족", weight: 8 }); return; }
    function hh(a, p, e) { var m = -Infinity; for (var i = e - p + 1; i <= e; i++) m = Math.max(m, a[i]); return m; }
    function ll(a, p, e) { var m = Infinity; for (var i = e - p + 1; i <= e; i++) m = Math.min(m, a[i]); return m; }
    var e = n - 1;
    var tenkan = (hh(highs, 9, e) + ll(lows, 9, e)) / 2;
    var kijun = (hh(highs, 26, e) + ll(lows, 26, e)) / 2;
    // 현재 시점 위에 걸린 구름(26일 전에 산출된 선행스팬)
    var e26 = e - 26;
    var spanA = null, spanB = null;
    if (e26 - 52 + 1 >= 0) {
      spanA = ((hh(highs, 9, e26) + ll(lows, 9, e26)) / 2 + (hh(highs, 26, e26) + ll(lows, 26, e26)) / 2) / 2;
      spanB = (hh(highs, 52, e26) + ll(lows, 52, e26)) / 2;
    }
    var sc = 50, det = "";
    if (spanA != null) {
      var top = Math.max(spanA, spanB), bot = Math.min(spanA, spanB);
      if (px > top) { sc = 90; det = "구름대 위(강세)"; }
      else if (px < bot) { sc = 20; det = "구름대 아래(약세)"; }
      else { sc = 50; det = "구름대 안(중립)"; }
      if (tenkan > kijun) sc += 8;
    } else { det = "산출 불가"; }
    subs.push({ key: "ichi", label: "일목균형표 구름대", score: _clamp(sc), detail: det, weight: 8 });
  })();

  // 8) 삼각수렴·돌파 — 변동성 수축 후 최근 고점 돌파 (라라리엔 참고: 돌파방향 매매)
  (function () {
    if (n < 40) { subs.push({ key: "brk", label: "삼각수렴·돌파", score: 50, detail: "-", weight: 10 }); return; }
    function rangePct(fromIdx, toIdx) {
      var hi = -Infinity, lo = Infinity;
      for (var i = fromIdx; i <= toIdx; i++) { hi = Math.max(hi, highs[i]); lo = Math.min(lo, lows[i]); }
      return (hi - lo) / lo * 100;
    }
    var recentRange = rangePct(n - 20, n - 1);
    var priorRange = rangePct(n - 40, n - 21);
    var contracting = recentRange < priorRange * 0.85;   // 변동성 수축(수렴)
    var hi20 = -Infinity;
    for (var i = n - 21; i < n - 1; i++) hi20 = Math.max(hi20, highs[i]);
    var breakout = px > hi20;                              // 직전 20일 고점 돌파
    var sc = 50;
    var det;
    if (contracting && breakout) { sc = 92; det = "수렴 후 상방 돌파"; }
    else if (breakout) { sc = 74; det = "신고가(20일) 돌파"; }
    else if (contracting) { sc = 60; det = "변동성 수축(대기)"; }
    else { sc = 45; det = "특이 신호 없음"; }
    subs.push({ key: "brk", label: "삼각수렴·돌파", score: sc, detail: det, weight: 10 });
  })();

  var wsum = 0, acc = 0;
  subs.forEach(function (s) { wsum += s.weight; acc += s.score * s.weight; });
  var total = wsum ? Math.round(acc / wsum) : 50;
  return { score: total, subs: subs, maStack: { ma5: ma5, ma20: ma20, ma60: ma60, ma120: ma120, px: px } };
}
/* TA 점수 → 색(빨강=강, 파랑=약; 한국식) */
function taScoreColor(sc) {
  if (sc >= 75) return "var(--up)";
  if (sc >= 60) return "#f0894a";
  if (sc >= 45) return "var(--muted)";
  if (sc >= 30) return "#6fa1ff";
  return "var(--dn)";
}
/* TA 지표 breakdown HTML (대중 인기 순서 그대로) */
function taBreakdownHTML(ta) {
  if (!ta) return '<div class="empty">기술적 지표를 계산할 데이터가 부족합니다.</div>';
  return '<div class="ta-list">' + ta.subs.map(function (s) {
    return '<div class="ta-row"><div class="ta-lbl">' + escapeHtml(s.label) + '</div>' +
      '<div class="ta-bar"><div class="ta-fill" style="width:' + s.score.toFixed(0) + '%;background:' + taScoreColor(s.score) + '"></div></div>' +
      '<div class="ta-sc" style="color:' + taScoreColor(s.score) + '">' + s.score.toFixed(0) + '</div>' +
      '<div class="ta-det">' + escapeHtml(s.detail) + "</div></div>";
  }).join("") + "</div>";
}

var PALETTE = ["#5b8cff", "#f0475a", "#f0b429", "#34d399", "#c084fc", "#22d3ee",
  "#fb923c", "#a3e635", "#f472b6", "#94a3b8", "#eab308", "#60a5fa"];

/* ---------- 구성종목/보유 카드 그리드 (일간 등락순) ----------
   clickable=true면 카드에 data-tk를 달고 커서를 포인터로 — 클릭 시 wireHoldingClicks()가 처리 */
function holdingsGridHTML(holdings, title, clickable) {
  var list = (holdings || []).slice().sort(function (a, b) { return num(b.r1d) - num(a.r1d); });
  if (!list.length) return "";
  var cards = list.map(function (h) {
    return '<div class="hold' + (clickable ? " clickable" : "") + '" data-tk="' + escapeHtml(h.ticker) + '" title="' + escapeHtml(h.name) + " " + escapeHtml(h.ticker) + '">' +
      '<div class="h-top"><span class="h-tk">' + escapeHtml(h.ticker.replace(/\.K[SQ]$/, "")) + '</span>' +
      '<span class="h-ret ' + pctClass(h.r1d) + '">' + fmtPct(h.r1d) + "</span></div>" +
      '<div class="h-nm">' + escapeHtml(h.name) + "</div>" +
      (h.spark ? sparklineSVG(h.spark, 100, 20) : "") +
      '<div class="h-sub">' + fmtPrice(h.price, h.ccy) + "</div></div>";
  }).join("");
  return '<h4 style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--accent);margin:18px 0 8px;font-weight:800">' +
    (title || "대표 종목") + ' <span class="muted small" style="text-transform:none;letter-spacing:0;font-weight:400">일간 등락순' +
    (clickable ? " · 클릭 = 개별 종목 보기" : "") + "</span></h4>" +
    '<div class="hold-grid">' + cards + "</div>";
}

/* ---------- 뉴스 리스트 (공용) ---------- */
function newsListHTML(news, title) {
  var list = news || [];
  var body = list.length
    ? "<ul style='margin-left:18px'>" + list.map(function (n) {
        return '<li style="margin:5px 0"><a href="' + escapeHtml(n.link) + '" target="_blank" rel="noopener">' +
          escapeHtml(n.title) + '</a> <span class="muted small">' + escapeHtml(n.source || "") +
          (n.date ? " · " + n.date : "") + "</span></li>";
      }).join("") + "</ul>"
    : '<div class="empty">최근 7일 뉴스가 없습니다.</div>';
  return '<h4 style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--accent);margin:18px 0 8px;font-weight:800">' +
    (title || "관련 뉴스") + "</h4>" + body;
}

/* ---------- 통계 모달(칩 + 기간탭 + 캔들 + 구성종목 + 뉴스 공용 골격) ----------
   cfg: {key(모달 재호출용 고유id), name, sub, price, priceCcy, r1d, chips:[{label,value,cls,per}],
         candles(전체 배열), holdings, news, holdingsTitle}
   기간 탭(1/3/6개월)은 상태를 모듈 전역에 저장해 재호출 시 유지한다. */
/* d = 달력 기준 일수(과거엔 거래일 개수였지만, 캔들이 최근 구간은 일봉·오래된 구간은 주봉으로 섞여 있어
   개수 기반 슬라이스 대신 날짜 기반 필터링을 쓴다 — 아래 statModalBody 참조) */
var STAT_WINDOWS = [
  { d: 30, l: "1개월" }, { d: 90, l: "3개월" }, { d: 182, l: "6개월" },
  { d: 365, l: "1년" }, { d: 1095, l: "3년" }, { d: 1825, l: "5년" }
];
var _statModalWin = 90;
var _statModalCfg = null;
var _statFinMode = "annual";  // 모달 내 재무 연간/분기 토글 상태
/* 재무 추이 섹션(연간/분기 토글 + 표). cfg.financials = {annual:[], quarterly:[]} 있을 때만 노출. */
function statFinSectionHTML(cfg) {
  var fin = cfg.financials;
  if (!fin || (!(fin.annual && fin.annual.length) && !(fin.quarterly && fin.quarterly.length))) return "";
  var isQ = _statFinMode === "quarterly";
  var rows = isQ ? fin.quarterly : fin.annual;
  if (!rows || !rows.length) { isQ = !isQ; rows = isQ ? fin.quarterly : fin.annual; }
  var ccy = (rows && rows[0] && rows[0].ccy) || "USD";
  return '<h4 style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--accent);margin:18px 0 8px;font-weight:800">재무 추이 ' +
    '<span class="muted small" style="text-transform:none;letter-spacing:0;font-weight:400">매출·영업이익·OPM·증가율</span></h4>' +
    '<div class="toggle" style="margin-bottom:8px">' +
    '<button data-sfin="annual" class="' + (!isQ ? "on" : "") + '">연간(' + ((fin.annual || []).length) + ')</button>' +
    '<button data-sfin="quarterly" class="' + (isQ ? "on" : "") + '">분기(' + ((fin.quarterly || []).length) + ')</button></div>' +
    '<div id="stat-fin-holder">' + financialsHTML(rows, isQ, ccy) + "</div>";
}
function statModalBody(cfg) {
  var chipsHtml = (cfg.chips || []).map(function (c) {
    return '<span class="chip' + (c.per ? " per" : "") + '">' + escapeHtml(c.label) +
      ' <b class="' + (c.cls || "") + '">' + escapeHtml(c.value) + "</b></span>";
  }).join("");
  var tabsHtml = STAT_WINDOWS.map(function (w) {
    return '<button data-swin="' + w.d + '" class="' + (w.d === _statModalWin ? "on" : "") + '">' + w.l + "</button>";
  }).join("");
  var all = cfg.candles || [];
  var asOf = all.length ? new Date(all[all.length - 1].d) : new Date();
  var cutoff = new Date(asOf.getTime() - _statModalWin * 86400000);
  var cutoffStr = cutoff.toISOString().slice(0, 10);
  var windowed = all.filter(function (c) { return c.d >= cutoffStr; });
  var chartHtml = candleChartSVG(windowed.length ? windowed : all, 820, 300);
  return '<div class="modal-chips">' + chipsHtml + "</div>" +
    (cfg.intro ? '<p class="note" style="margin:0 0 12px;max-width:none">' + escapeHtml(cfg.intro) + "</p>" : "") +
    '<div class="toggle" style="margin-bottom:10px">' + tabsHtml + "</div>" +
    chartHtml +
    (cfg.ta ? statTaSectionHTML(cfg.ta) : "") +
    statFinSectionHTML(cfg) +
    (cfg.holdings ? holdingsGridHTML(cfg.holdings, cfg.holdingsTitle, !!cfg.onHoldingClick) : "") +
    (cfg.news !== undefined ? newsListHTML(cfg.news) : "");
}
function statTaSectionHTML(ta) {
  if (!ta) return "";
  return '<h4 style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--accent);margin:18px 0 8px;font-weight:800">기술적 분석 ' +
    '<span class="muted small" style="text-transform:none;letter-spacing:0;font-weight:400">대중이 많이 보는 순서 · 종합 <b style="color:' + taScoreColor(ta.score) + '">' + ta.score + '점</b>/100</span></h4>' +
    taBreakdownHTML(ta);
}
function wireHoldingClicks(cfg) {
  if (!cfg.onHoldingClick) return;
  $qa("#modal-back .m-body .hold[data-tk]").forEach(function (h) {
    h.onclick = function () { cfg.onHoldingClick(h.dataset.tk); };
  });
}
function wireStatFinToggle() {
  $qa("#modal-back [data-sfin]").forEach(function (b) {
    b.onclick = function () {
      _statFinMode = b.dataset.sfin;
      var fin = _statModalCfg && _statModalCfg.financials;
      if (!fin) return;
      var isQ = _statFinMode === "quarterly";
      var rows = isQ ? fin.quarterly : fin.annual;
      var ccy = (rows && rows[0] && rows[0].ccy) || "USD";
      var holder = document.querySelector("#modal-back #stat-fin-holder");
      if (holder) holder.innerHTML = financialsHTML(rows, isQ, ccy);
      $qa("#modal-back [data-sfin]").forEach(function (x) { x.classList.toggle("on", x.dataset.sfin === _statFinMode); });
    };
  });
}
function openStatModal(cfg) {
  _statModalCfg = cfg;
  _statModalWin = 90;
  _statFinMode = "annual";
  var priceHtml = '<span class="px">' + fmtPrice(cfg.price, cfg.priceCcy) + "</span>" +
    (cfg.r1d != null ? ' <span class="' + pctClass(cfg.r1d) + '" style="font-weight:700">' + fmtPct(cfg.r1d) + "</span>" : "") +
    '<button class="cap-btn" onclick="captureStatChart()" title="차트를 클립보드에 복사">복사</button>';
  openModal(
    escapeHtml(cfg.name) + (cfg.sub ? ' <span class="muted small" style="font-weight:400">' + escapeHtml(cfg.sub) + "</span>" : ""),
    statModalBody(cfg),
    priceHtml
  );
  $qa("[data-swin]").forEach(function (b) {
    b.onclick = function () { _statModalWin = +b.dataset.swin; rerenderStatModal(); };
  });
  wireHoldingClicks(cfg);
  wireStatFinToggle();
}
function rerenderStatModal() {
  if (!_statModalCfg) return;
  var mb = document.querySelector("#modal-back .m-body");
  if (mb) mb.innerHTML = statModalBody(_statModalCfg);
  $qa("[data-swin]").forEach(function (b) {
    b.onclick = function () { _statModalWin = +b.dataset.swin; rerenderStatModal(); };
  });
  wireHoldingClicks(_statModalCfg);
  wireStatFinToggle();
}

/* ---------- 차트 클립보드 복사 ----------
   모달 안의 캔들 SVG를 헤더(이름·가격·수익률)와 함께 PNG로 합성해 클립보드에 복사한다.
   클립보드 미지원/거부 시 파일 다운로드로 대체한다. */
function buildChartPNGBlob() {
  return new Promise(function (resolve, reject) {
    var modal = document.getElementById("modal-back");
    var svg = modal && modal.querySelector(".m-body svg");
    if (!svg) { reject(new Error("no chart")); return; }
    var cs = getComputedStyle(document.documentElement);
    function cv(name, fallback) { var v = cs.getPropertyValue(name).trim(); return v || fallback; }
    var C = { bg: cv("--bg2", "#10141d"), text: cv("--text", "#e6e9f0"), muted: cv("--muted", "#8b93a7"),
      up: cv("--up", "#f0475a"), dn: cv("--dn", "#3d7eff"), border: cv("--border", "#232a3a") };
    var vb = svg.viewBox && svg.viewBox.baseVal;
    var cw = (vb && vb.width) || svg.clientWidth || 820;
    var ch = (vb && vb.height) || svg.clientHeight || 300;
    var clone = svg.cloneNode(true);
    clone.setAttribute("width", cw); clone.setAttribute("height", ch);
    var s = new XMLSerializer().serializeToString(clone)
      .replace(/var\(--up\)/g, C.up).replace(/var\(--dn\)/g, C.dn)
      .replace(/var\(--border\)/g, C.border).replace(/var\(--muted\)/g, C.muted);
    if (!/xmlns=/.test(s)) s = s.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');

    var h3 = modal.querySelector(".m-head h3");
    var name = h3 ? (h3.childNodes[0].textContent || "").trim() : "";
    var pxEl = modal.querySelector(".m-head .px");
    var price = pxEl ? pxEl.textContent.trim() : "";
    var retEl = pxEl ? pxEl.nextElementSibling : null;
    var ret = retEl ? retEl.textContent.trim() : "";
    var retColor = retEl && retEl.classList.contains("up") ? C.up : retEl && retEl.classList.contains("dn") ? C.dn : C.muted;

    var SCALE = 2, W = 900, pad = 28, headH = 64, footH = 26;
    var chartW = W - pad * 2, chartH = Math.round(chartW * ch / cw);
    var H = pad + headH + chartH + footH;
    var canvas = document.createElement("canvas");
    canvas.width = W * SCALE; canvas.height = H * SCALE;
    var x = canvas.getContext("2d");
    x.scale(SCALE, SCALE);
    x.fillStyle = C.bg; x.fillRect(0, 0, W, H);
    x.textBaseline = "alphabetic";
    x.fillStyle = C.text; x.font = "800 22px Pretendard, sans-serif"; x.fillText(name, pad, pad + 20);
    x.fillStyle = C.text; x.font = "700 18px Pretendard, sans-serif"; x.fillText(price, pad, pad + 44);
    var pw = x.measureText(price).width;
    x.fillStyle = retColor; x.font = "700 14px Pretendard, sans-serif"; x.fillText(ret, pad + pw + 10, pad + 44);
    x.strokeStyle = C.border; x.lineWidth = 1;
    x.beginPath(); x.moveTo(pad, pad + headH - 6); x.lineTo(W - pad, pad + headH - 6); x.stroke();

    var url = URL.createObjectURL(new Blob([s], { type: "image/svg+xml;charset=utf-8" }));
    var img = new Image();
    img.onload = function () {
      x.drawImage(img, pad, pad + headH, chartW, chartH);
      URL.revokeObjectURL(url);
      x.fillStyle = C.muted; x.font = "400 10.5px Pretendard, sans-serif";
      x.fillText("etf-flow-tracker · " + new Date().toISOString().slice(0, 10), pad, H - 10);
      canvas.toBlob(function (b) { b ? resolve(b) : reject(new Error("toBlob failed")); }, "image/png");
    };
    img.onerror = function () { URL.revokeObjectURL(url); reject(new Error("img error")); };
    img.src = url;
  });
}
function flashCapBtn(msg) {
  var b = document.querySelector("#modal-back .cap-btn");
  if (!b) return;
  if (b.dataset.label == null) b.dataset.label = b.textContent;
  b.textContent = msg;
  clearTimeout(b._t);
  b._t = setTimeout(function () { b.textContent = b.dataset.label; }, 1600);
}
function downloadChartPNG(blob) {
  var h3 = document.querySelector("#modal-back .m-head h3");
  var name = (h3 ? h3.textContent : "chart").replace(/[^\w.-]/g, "_").slice(0, 40) || "chart";
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name + "_" + new Date().toISOString().slice(0, 10) + ".png";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(function () { URL.revokeObjectURL(a.href); }, 1500);
}
/* ---------- 스퀘리파이드 트리맵 ----------
   items: [{key, label, value(면적 가중치), ret(색), group}] — group이 있으면 그룹별로 먼저 분할.
   반환: [{key, label, ret, x, y, w, h}] (0~1 정규화 좌표) */
function squarify(items, x, y, w, h) {
  var out = [];
  var list = items.slice().sort(function (a, b) { return b.value - a.value; });
  var total = list.reduce(function (s, it) { return s + it.value; }, 0);
  if (!total) return out;
  function worst(row, side) {
    var sum = row.reduce(function (s, r) { return s + r.area; }, 0);
    var mx = Math.max.apply(null, row.map(function (r) { return r.area; }));
    var mn = Math.min.apply(null, row.map(function (r) { return r.area; }));
    var s2 = sum * sum, side2 = side * side;
    return Math.max((side2 * mx) / s2, s2 / (side2 * mn));
  }
  function layoutRow(row, rect) {
    var sum = row.reduce(function (s, r) { return s + r.area; }, 0);
    var horiz = rect.w >= rect.h;
    var side = horiz ? rect.h : rect.w;
    var thick = sum / side;
    var off = 0;
    row.forEach(function (r) {
      var len = r.area / thick;
      if (horiz) out.push({ it: r.it, x: rect.x, y: rect.y + off, w: thick, h: len });
      else out.push({ it: r.it, x: rect.x + off, y: rect.y, w: len, h: thick });
      off += len;
    });
    if (horiz) return { x: rect.x + thick, y: rect.y, w: rect.w - thick, h: rect.h };
    return { x: rect.x, y: rect.y + thick, w: rect.w, h: rect.h - thick };
  }
  var rect = { x: x, y: y, w: w, h: h };
  var row = [], areaScale = (w * h) / total;
  list.forEach(function (it) {
    var r = { it: it, area: it.value * areaScale };
    var side = Math.min(rect.w, rect.h);
    if (!row.length) { row.push(r); return; }
    var before = worst(row, side);
    row.push(r);
    if (worst(row, side) > before) {
      row.pop();
      rect = layoutRow(row, rect);
      row = [r];
    }
  });
  if (row.length) layoutRow(row, rect);
  return out.map(function (o) {
    return { key: o.it.key, label: o.it.label, ret: o.it.ret, x: o.x, y: o.y, w: o.w, h: o.h };
  });
}

/* 수익률 → 트리맵 셀 색 (한국식: 상승 빨강 / 하락 파랑, 강도 스케일) */
function treemapColor(v, cap) {
  v = num(v); cap = cap || 6;
  var t = Math.max(-1, Math.min(1, v / cap));
  var a = 0.25 + Math.abs(t) * 0.6;
  if (t > 0) return "rgba(200,45,65," + a.toFixed(3) + ")";
  if (t < 0) return "rgba(40,95,220," + a.toFixed(3) + ")";
  return "rgba(90,98,115,0.35)";
}

/* 그룹(섹터) → 종목 2단 트리맵을 container(#treemap-box 등)에 렌더.
   stocks: [{ticker,label,mcap,ret,group}], onClick(ticker) */
function renderTreemap(container, stocks, cap, onClick) {
  var byGroup = {};
  stocks.forEach(function (s) {
    (byGroup[s.group] = byGroup[s.group] || []).push(s);
  });
  var groups = Object.keys(byGroup).map(function (g) {
    return { key: g, label: g, ret: 0, value: byGroup[g].reduce(function (t, s) { return t + s.mcap; }, 0) };
  });
  var W = container.clientWidth || 1200, H = container.clientHeight || 460;
  var gRects = squarify(groups, 0, 0, W, H);
  var html = "";
  gRects.forEach(function (gr) {
    var inner = byGroup[gr.key].map(function (s) {
      return { key: s.ticker, label: s.label, ret: s.ret, value: s.mcap };
    });
    var cells = squarify(inner, gr.x, gr.y, gr.w, gr.h);
    cells.forEach(function (c) {
      var showTk = c.w > 42 && c.h > 26;
      var showRet = c.w > 52 && c.h > 40;
      var fs = Math.max(9, Math.min(16, Math.sqrt(c.w * c.h) / 6));
      html += '<div class="tm-cell" data-t="' + escapeHtml(c.key) + '" title="' + escapeHtml(c.label) +
        " " + fmtPct(c.ret) + '" style="left:' + c.x.toFixed(1) + "px;top:" + c.y.toFixed(1) +
        "px;width:" + c.w.toFixed(1) + "px;height:" + c.h.toFixed(1) + "px;background:" + treemapColor(c.ret, cap) + '">' +
        (showTk ? '<span class="tm-tk" style="font-size:' + fs.toFixed(0) + 'px">' + escapeHtml(c.key.replace(/\.K[SQ]$/, "").replace(/\.[A-Z]+$/, "")) + "</span>" : "") +
        (showRet ? '<span class="tm-ret" style="font-size:' + Math.max(8, fs - 3).toFixed(0) + 'px">' + fmtPct(c.ret, 1) + "</span>" : "") +
        "</div>";
    });
    if (gr.w > 70 && gr.h > 30) {
      html += '<span class="tm-sector-label" style="left:' + gr.x.toFixed(1) + "px;top:" + gr.y.toFixed(1) + 'px">' +
        escapeHtml(gr.label) + "</span>";
    }
  });
  container.innerHTML = html;
  $qa(".tm-cell", container).forEach(function (c) {
    c.onclick = function () { if (onClick) onClick(c.dataset.t); };
  });
}

/* ---------- 재무 시각화 (매출/영업이익 막대 + 증가율·OPM) ----------
   rows: [{date, rev, op, opm, rev_yoy, op_yoy, rev_qoq?, op_qoq?, ccy}] 오름차순.
   isQuarter이면 QoQ 열 추가. 통화는 rows[0].ccy. */
function fmtBig(v, ccy) {
  if (v == null) return "–";
  var sym = { USD: "$", KRW: "₩", EUR: "€", JPY: "¥", TWD: "NT$", GBP: "£" }[ccy] || "";
  var abs = Math.abs(v);
  // v는 백만 단위
  if (abs >= 1e6) return sym + (v / 1e6).toFixed(2) + "조";        // 백만*1e6 = 조
  if (abs >= 1e3) return sym + (v / 1e3).toFixed(1) + "십억";
  return sym + Math.round(v).toLocaleString();
}
function financialsHTML(rows, isQuarter, ccy) {
  if (!rows || rows.length < 1) {
    return '<div class="empty">재무 데이터가 아직 없습니다 (다음 자동 갱신 때 수집됩니다).</div>';
  }
  function label(d) { return isQuarter ? d.slice(2, 7).replace("-", "/") : d.slice(0, 4); }
  // 지표를 행으로, 기간을 열로 — 오래된 기간이 왼쪽
  var cols = rows.map(function (r) { return "<th>" + label(r.date) + "</th>"; }).join("");
  function metricRow(name, cls, cells) {
    return "<tr><td class='l" + (cls ? " " + cls : "") + "'>" + name + "</td>" + cells.join("") + "</tr>";
  }
  var revRow = metricRow("<b>매출</b>", "", rows.map(function (r) { return "<td>" + fmtBig(r.rev, ccy) + "</td>"; }));
  var revYoyRow = metricRow("YoY", "muted small", rows.map(function (r) { return "<td>" + (r.rev_yoy != null ? pctSpan(r.rev_yoy, 1) : "–") + "</td>"; }));
  var revQoqRow = isQuarter ? metricRow("QoQ", "muted small", rows.map(function (r) { return "<td>" + (r.rev_qoq != null ? pctSpan(r.rev_qoq, 1) : "–") + "</td>"; })) : "";
  var opRow = metricRow("<b>영업이익</b>", "", rows.map(function (r) { return "<td>" + fmtBig(r.op, ccy) + "</td>"; }));
  var opmRow = metricRow("OPM", "muted small", rows.map(function (r) { return "<td>" + (r.opm != null ? r.opm.toFixed(1) + "%" : "–") + "</td>"; }));
  var opYoyRow = metricRow("YoY", "muted small", rows.map(function (r) { return "<td>" + (r.op_yoy != null ? pctSpan(r.op_yoy, 1) : "–") + "</td>"; }));
  var opQoqRow = isQuarter ? metricRow("QoQ", "muted small", rows.map(function (r) { return "<td>" + (r.op_qoq != null ? pctSpan(r.op_qoq, 1) : "–") + "</td>"; })) : "";
  return '<div class="tbl-wrap"><table class="tbl fin-tbl" style="min-width:0;font-size:12px">' +
    "<tr><th class='l'>기간</th>" + cols + "</tr>" +
    revRow + revYoyRow + revQoqRow + opRow + opmRow + opYoyRow + opQoqRow +
    "</table></div>";
}

/* ---------- ETF 상세 모달 (공용: data.json의 etf 객체 하나를 받아 통계모달을 연다) ----------
   onHoldingClick(ticker)를 넘기면 대표 구성종목 카드가 클릭 가능해지고, 클릭 시 이 콜백이 호출된다. */
function openEtfDetailModal(e, tk, onHoldingClick) {
  var ccy = /\.K[SQ]$/.test(tk) ? "₩" : "$";
  openStatModal({
    name: e.name,
    sub: tk.replace(/\.K[SQ]$/, "") + (e.group ? " · " + e.group : ""),
    price: e.price, priceCcy: ccy, r1d: e.r1d,
    chips: [
      { label: "1주", value: fmtPct(e.r1w), cls: pctClass(e.r1w) },
      { label: "1개월", value: fmtPct(e.r1m), cls: pctClass(e.r1m) },
      { label: "3개월", value: fmtPct(e.r3m), cls: pctClass(e.r3m) },
      { label: "YTD", value: fmtPct(e.ytd), cls: pctClass(e.ytd) },
      { label: "거래대금", value: "×" + num(e.vol_ratio).toFixed(2), cls: e.vol_ratio > 1.2 ? "up" : "" },
      { label: "52주 고점대비", value: fmtPct(e.from_high, 1), cls: pctClass(e.from_high) }
    ],
    candles: e.candles, holdings: e.holdings, holdingsTitle: "대표 구성종목", news: e.news,
    onHoldingClick: onHoldingClick
  });
}

/* ---------- 메가캡 개별 종목 모달 (공용: megacap.json의 종목 객체 하나로 통계모달을 연다) ---------- */
function megaCcySym(tk) { return /\.K[SQ]$/.test(tk) ? "₩" : /\.(T|TW|HK|NS|SR|L|PA|DE|AS|SW|MI|MC|ST|OL|CO)$/.test(tk) ? "" : "$"; }
function megaDayRet(s) {
  if (s && typeof s.r1d === "number" && s.r1d !== 0) return s.r1d;
  var c = s && s.candles;
  if (c && c.length >= 2) { var a = c[c.length - 1].c, b = c[c.length - 2].c; return b ? +((a / b - 1) * 100).toFixed(2) : 0; }
  return 0;
}
function openMegaStockModal(tk, mega, fin) {
  if (!mega) return;
  var chips = [
    { label: "1주", value: fmtPct(mega.r1w), cls: pctClass(mega.r1w) },
    { label: "1개월", value: fmtPct(mega.r1m), cls: pctClass(mega.r1m) },
    { label: "YTD", value: fmtPct(mega.ytd), cls: pctClass(mega.ytd) },
    { label: "52주 고점대비", value: fmtPct(mega.from_high, 1), cls: pctClass(mega.from_high) }
  ];
  if (mega.mcap_usd) chips.push({ label: "시총", value: fmtMcap(mega.mcap_usd), cls: "" });
  if (mega.pe_now != null || mega.pe_next != null) {
    chips.push({ label: "선행PER", per: true, cls: "",
      value: (mega.pe_now != null ? "올해 " + mega.pe_now : "") + (mega.pe_now != null && mega.pe_next != null ? " → " : "") + (mega.pe_next != null ? "내년 " + mega.pe_next : "") });
  }
  openStatModal({
    name: mega.name, sub: tk.replace(/\.[A-Z]+$/, "") + (mega.sector ? " · " + mega.sector : ""),
    price: mega.price, priceCcy: megaCcySym(tk), r1d: megaDayRet(mega),
    chips: chips, candles: mega.candles, news: mega.news, financials: fin,
    ta: computeTA(mega.candles)
  });
}

function captureStatChart() {
  var canClip = !!(navigator.clipboard && window.ClipboardItem && window.isSecureContext);
  if (canClip) {
    navigator.clipboard.write([new ClipboardItem({ "image/png": buildChartPNGBlob() })])
      .then(function () { flashCapBtn("복사됨 ✓"); })
      .catch(function () {
        buildChartPNGBlob().then(function (b) { downloadChartPNG(b); flashCapBtn("저장됨 ↓"); }).catch(function () { flashCapBtn("실패"); });
      });
    return;
  }
  buildChartPNGBlob().then(function (b) { downloadChartPNG(b); flashCapBtn("저장됨 ↓"); }).catch(function () { flashCapBtn("실패"); });
}
