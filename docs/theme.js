/* 공통 상단 내비게이션 + 유틸 — 모든 페이지에서 로드 */
(function () {
  var PAGES = [
    ["index.html", "섹터 대시보드"],
    ["megacap.html", "글로벌 메가캡"],
    ["perspective.html", "핵심 테제 트래킹"],
    ["worldflow.html", "세상 흐름 파악"],
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
      links + "</div>";
  }
})();

/* 전역 헬퍼 */
function $q(sel, root) { return (root || document).querySelector(sel); }
function $qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
