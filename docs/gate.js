/* ============================================================
   접근 비밀번호 게이트 (클라이언트 사이드)
   - 링크가 공개돼도 비밀번호(key)를 아는 사람만 사이트를 볼 수 있습니다.
   - 비밀번호 평문은 저장하지 않고 SHA-256 해시만 비교합니다.
   - 한 번 맞추면 그 브라우저에는 기억됩니다(localStorage).

   ▶ 비밀번호 바꾸는 법:
     1) 새 비밀번호의 SHA-256 해시를 구합니다.
        (예: 파이썬  python -c "import hashlib;print(hashlib.sha256('새비번'.encode()).hexdigest())")
     2) 아래 GATE_HASH 값을 그 해시로 교체하고,
     3) GATE_VER 값을 아무 다른 숫자로 바꾸면(기존에 로그인된 사람도 다시 입력하게 됨),
        각 HTML의 gate.js?v= 뒤 숫자도 함께 올려 배포하세요.
   ============================================================ */
(function () {
  "use strict";

  // 현재 비밀번호: etf2026  (반드시 원하는 값으로 교체하세요)
  var GATE_HASH = "5ec37e098056971a3cd206c5883f07b0e5597836e9467c4a47a336b03a346195";
  var GATE_VER  = "1"; // 값을 바꾸면 모든 사용자가 재입력
  var STORE_KEY = "etf_gate_ok_v" + GATE_VER;

  // 이미 통과한 브라우저면 아무것도 안 함
  try {
    if (localStorage.getItem(STORE_KEY) === GATE_HASH) return;
  } catch (e) {}

  function sha256Hex(str) {
    var enc = new TextEncoder().encode(str);
    return crypto.subtle.digest("SHA-256", enc).then(function (buf) {
      return Array.prototype.map
        .call(new Uint8Array(buf), function (b) {
          return ("0" + b.toString(16)).slice(-2);
        })
        .join("");
    });
  }

  // 콘텐츠가 잠깐 비치지 않도록 즉시 스크롤 잠금 + 오버레이 삽입
  var docEl = document.documentElement;
  var prevOverflow = docEl.style.overflow;
  docEl.style.overflow = "hidden";

  var ov = document.createElement("div");
  ov.id = "__gate_overlay";
  ov.setAttribute(
    "style",
    [
      "position:fixed",
      "inset:0",
      "z-index:2147483647",
      "background:radial-gradient(1200px 700px at 50% -10%, #16202f 0%, #0b0e14 60%, #070a10 100%)",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Malgun Gothic',sans-serif",
      "color:#e8edf5",
    ].join(";")
  );

  ov.innerHTML =
    '<div style="width:min(92vw,380px);background:#0f1420;border:1px solid #22314a;border-radius:16px;padding:30px 26px 26px;box-shadow:0 24px 60px rgba(0,0,0,.55)">' +
      '<div style="font-size:34px;text-align:center;line-height:1">🔒</div>' +
      '<div style="text-align:center;margin-top:12px;font-size:19px;font-weight:700;letter-spacing:-.2px">비공개 페이지</div>' +
      '<div style="text-align:center;margin-top:8px;font-size:13px;color:#93a1b8;line-height:1.55">접근하려면 비밀번호가 필요합니다.<br>비밀번호는 운영자에게 문의하세요.</div>' +
      '<input id="__gate_input" type="password" autocomplete="off" placeholder="비밀번호 입력" ' +
        'style="width:100%;box-sizing:border-box;margin-top:18px;padding:13px 14px;font-size:15px;color:#e8edf5;background:#0a0f18;border:1px solid #2b3a55;border-radius:10px;outline:none">' +
      '<div id="__gate_err" style="height:18px;margin-top:8px;font-size:12.5px;color:#f0475a;text-align:center"></div>' +
      '<button id="__gate_btn" ' +
        'style="width:100%;margin-top:6px;padding:13px;font-size:15px;font-weight:700;color:#fff;background:#3d7eff;border:0;border-radius:10px;cursor:pointer">입장</button>' +
    '</div>';

  function mount() {
    (document.body || docEl).appendChild(ov);
    var input = document.getElementById("__gate_input");
    var btn = document.getElementById("__gate_btn");
    var err = document.getElementById("__gate_err");
    if (input) input.focus();

    function fail() {
      err.textContent = "비밀번호가 올바르지 않습니다.";
      input.value = "";
      input.focus();
      ov.animate(
        [
          { transform: "translateX(0)" },
          { transform: "translateX(-7px)" },
          { transform: "translateX(7px)" },
          { transform: "translateX(0)" },
        ],
        { duration: 220 }
      );
    }

    function submit() {
      var val = input.value || "";
      if (!val) {
        input.focus();
        return;
      }
      err.textContent = "";
      sha256Hex(val).then(function (hex) {
        if (hex === GATE_HASH) {
          try {
            localStorage.setItem(STORE_KEY, GATE_HASH);
          } catch (e) {}
          docEl.style.overflow = prevOverflow;
          ov.remove();
        } else {
          fail();
        }
      });
    }

    btn.addEventListener("click", submit);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") submit();
    });
  }

  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();
