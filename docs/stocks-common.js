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
function openModal(titleHtml, bodyHtml) {
  closeModal();
  var back = document.createElement("div");
  back.className = "modal-back";
  back.id = "modal-back";
  back.innerHTML =
    '<div class="modal"><div class="m-head"><h3>' + titleHtml +
    '</h3><button class="m-close" onclick="closeModal()">닫기 ✕</button></div>' +
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

var PALETTE = ["#5b8cff", "#f0475a", "#f0b429", "#34d399", "#c084fc", "#22d3ee",
  "#fb923c", "#a3e635", "#f472b6", "#94a3b8", "#eab308", "#60a5fa"];
