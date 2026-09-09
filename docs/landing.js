(function () {
  "use strict";
  var KEY = "vantage-route-motion";
  function remember(value) { try { sessionStorage.setItem(KEY, value); } catch (e) {} }
  function takeMotion() { try { var value = sessionStorage.getItem(KEY); sessionStorage.removeItem(KEY); return value; } catch (e) { return null; } }
  function playReturn() { document.body.classList.remove("is-leaving"); document.body.classList.add("is-returning"); setTimeout(function () { document.body.classList.remove("is-returning"); }, 750); }
  if (takeMotion() === "back") playReturn();
  window.addEventListener("pageshow", function (event) { var nav = performance.getEntriesByType && performance.getEntriesByType("navigation")[0]; if (event.persisted || (nav && nav.type === "back_forward")) playReturn(); });
  document.querySelectorAll("a[data-route]").forEach(function (link) {
    link.addEventListener("click", function (event) { if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return; event.preventDefault(); remember("enter"); document.body.classList.add("is-leaving"); setTimeout(function () { location.href = link.href; }, 390); });
    link.addEventListener("pointermove", function (event) { var rect = link.getBoundingClientRect(); link.style.setProperty("--mx", (event.clientX - rect.left) + "px"); link.style.setProperty("--my", (event.clientY - rect.top) + "px"); });
  });
  var portfolioBrief = document.getElementById("landing-portfolio-brief");
  if (portfolioBrief && window.PortfolioStore) {
    var data = window.PortfolioStore.load();
    portfolioBrief.innerHTML = '<span class="lp-label">PORTFOLIO<br>STATUS</span>' + data.accounts.slice(0, 2).map(function (account) {
      var total = window.PortfolioStore.aggregate(data, account.id).reduce(function (sum, h) { return sum + (h.valueKrw || 0); }, 0);
      return '<span class="lp-account"><span>' + String(account.name).replace(/</g, "&lt;").replace(/>/g, "&gt;") + '</span><b>' + (total ? '₩' + Math.round(total).toLocaleString("ko-KR") : '기록 추가') + '</b></span>';
    }).join("") + '<i class="lp-go">↗</i>';
  }
  var canvas = document.getElementById("pulse-chart"); if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d"), width = 0, height = 0, phase = 0;
  function resize() { var box = canvas.getBoundingClientRect(), scale = Math.min(window.devicePixelRatio || 1, 2); width = Math.max(1, box.width); height = Math.max(1, box.height); canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale); ctx.setTransform(scale, 0, 0, scale, 0, 0); }
  function line(offset, color, amp, speed) { ctx.beginPath(); for (var x = -4; x <= width + 4; x += 4) { var wave = Math.sin(x / 74 + phase * speed + offset) * amp + Math.sin(x / 23 + phase * speed * .7 + offset) * amp * .22; var trend = Math.sin(x / width * 5 + offset) * height * .07; var y = height * .54 + wave + trend; if (x < 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); } ctx.strokeStyle = color; ctx.stroke(); }
  function draw() { ctx.clearRect(0, 0, width, height); ctx.lineWidth = 1; line(0, "rgba(84,126,255,.28)", height * .16, .42); ctx.lineWidth = 1.6; line(1.7, "rgba(163,192,255,.92)", height * .115, .61); ctx.lineWidth = 1; line(3.9, "rgba(240,180,41,.32)", height * .07, .33); phase += .009; requestAnimationFrame(draw); }
  resize(); window.addEventListener("resize", resize, { passive: true }); draw();
})();
