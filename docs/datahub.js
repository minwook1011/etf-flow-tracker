(function () {
  "use strict";
  var DATA = {
    korea: { label: "한국", code: "KOR", series: [
      ["반도체 수출", "수출액 · 물량 · 단가", ["삼성전자", "SK하이닉스"]],
      ["메모리 가격", "DRAM · NAND · 계약가격", ["삼성전자", "SK하이닉스"]],
      ["전력 수요", "산업용 전력 · 데이터센터", ["삼성전자", "한전"]],
      ["외국인 수급", "코스피 · 업종별 순매수", ["삼성전자", "SK하이닉스"]],
      ["제조업 가동률", "생산 · 재고 · 출하", ["삼성전자", "현대차"]]
    ] },
    usa: { label: "미국", code: "USA", series: [
      ["AI 데이터센터 CAPEX", "하이퍼스케일러 투자 · 가이던스", ["NVIDIA", "Amazon", "Microsoft"]],
      ["GPU 임대료", "GPU별 일간 임대 지수", ["NVIDIA", "CoreWeave"]],
      ["클라우드 사용량", "AWS · Azure · GCP 수요", ["Amazon", "Microsoft"]],
      ["AI 서비스 이용자", "MAU · 트래픽 · 구독", ["Microsoft", "NVIDIA"]],
      ["기업 IT 지출", "소프트웨어 · 인프라 지출", ["Microsoft", "Amazon"]]
    ] },
    japan: { label: "일본", code: "JPN", series: [
      ["반도체 장비 수주", "장비 주문 · 출하 · 가동률", ["TSMC", "삼성전자", "NVIDIA"]],
      ["로봇·자동화", "산업용 로봇 · 공장 자동화", ["삼성전자", "현대차"]],
      ["일본 수출", "기계 · 전자부품 · 소재", ["TSMC", "삼성전자"]],
      ["엔화·금리", "USD/JPY · 국채금리 · 정책", ["삼성전자", "TSMC"]],
      ["전력·소재", "전력 인프라 · 핵심 소재", ["TSMC", "NVIDIA"]]
    ] },
    macro: { label: "매크로", code: "MAC", series: [
      ["달러·환율", "DXY · 원/달러 · 엔/달러", ["삼성전자", "TSMC", "Amazon"]],
      ["금리·유동성", "국채금리 · 실질금리 · 유동성", ["NVIDIA", "Microsoft", "Amazon"]],
      ["신용 스프레드", "회사채 · 하이일드 · 금융여건", ["삼성전자", "NVIDIA"]],
      ["원자재", "구리 · 유가 · 희토류", ["TSMC", "삼성전자"]],
      ["글로벌 교역", "운임 · PMI · 수출입", ["삼성전자", "TSMC"]]
    ] },
    industry: { label: "산업", code: "IND", series: [
      ["TSMC 월매출", "월매출 · YoY · 공정 믹스", ["TSMC", "삼성전자", "NVIDIA"]],
      ["첨단 패키징", "패키징 · 기판 · 테스트", ["TSMC", "삼성전자", "SK하이닉스"]],
      ["AI 데이터센터", "CAPEX · 서버 출하 · 전력", ["NVIDIA", "Amazon", "Microsoft"]],
      ["GPU 임대료", "GPU별 일간 임대 지수", ["NVIDIA", "CoreWeave"]],
      ["DRAM · NAND 가격", "현물 · 계약가격 · 재고", ["삼성전자", "SK하이닉스"]]
    ] }
  };
  var COMPANIES = {
    "삼성전자": ["한국 반도체 수출", "메모리 가격", "TSMC 월매출", "DRAM · NAND 가격", "달러·환율"],
    "SK하이닉스": ["한국 반도체 수출", "메모리 가격", "TSMC 월매출", "DRAM · NAND 가격", "첨단 패키징"],
    "TSMC": ["TSMC 월매출", "반도체 장비 수주", "첨단 패키징", "일본 수출", "전력·소재"],
    "NVIDIA": ["AI 데이터센터 CAPEX", "GPU 임대료", "TSMC 월매출", "AI 데이터센터", "금리·유동성"],
    "Amazon": ["AI 데이터센터 CAPEX", "클라우드 사용량", "기업 IT 지출", "달러·환율", "금리·유동성"],
    "Microsoft": ["AI 데이터센터 CAPEX", "AI 서비스 이용자", "클라우드 사용량", "기업 IT 지출", "금리·유동성"]
  };
  var activeCountry = "korea", activeCompany = "삼성전자", activeSeries = null;
  var countryHost = document.getElementById("country-tabs"), seriesHost = document.getElementById("series-grid");
  function renderCountries() {
    countryHost.innerHTML = Object.keys(DATA).map(function (key) { return '<button class="country-tab' + (key === activeCountry ? ' on' : '') + '" type="button" data-country="' + key + '">' + DATA[key].label + '</button>'; }).join("");
    countryHost.querySelectorAll("button").forEach(function (button) { button.onclick = function () { activeCountry = button.dataset.country; activeSeries = null; renderCountries(); renderSeries(); renderWorkbench(); }; });
  }
  function renderSeries() {
    var group = DATA[activeCountry];
    seriesHost.innerHTML = group.series.map(function (item, index) {
      var selected = activeSeries && activeSeries.name === item[0];
      return '<button class="series-card' + (selected ? ' selected' : '') + '" type="button" style="animation-delay:' + (index * 65) + 'ms" data-index="' + index + '"><span class="country-code">' + group.code + ' · SERIES 0' + (index + 1) + '</span><b>' + item[0] + '</b><p>' + item[1] + '</p><span class="series-state"><i></i>' + (selected ? '차트에 추가됨' : '출처 연결 대기') + '</span></button>';
    }).join("");
    seriesHost.querySelectorAll("button").forEach(function (button) { button.onclick = function () { var item = group.series[Number(button.dataset.index)]; activeSeries = { name: item[0], desc: item[1] }; renderSeries(); renderWorkbench(); }; });
  }
  function renderCompanyOptions() {
    var names = {};
    Object.keys(COMPANIES).forEach(function (name) { names[name] = true; });
    Object.keys(DATA).forEach(function (key) {
      DATA[key].series.forEach(function (series) { (series[2] || []).forEach(function (name) { names[name] = true; }); });
    });
    document.getElementById("company-options").innerHTML = Object.keys(names).sort().map(function (name) { return '<option value="' + name + '"></option>'; }).join("");
  }
  function selectCompany() {
    var input = document.getElementById("company-search"), name = input.value.trim();
    if (!name) return;
    activeCompany = name; input.value = name; renderWorkbench();
  }
  function renderWorkbench() {
    var links = COMPANIES[activeCompany] || ["연관 지표 등록 대기", "기업 실적 데이터 연결 대기", "주가와 함께 볼 외부 지표 추가 가능"];
    document.getElementById("chart-company").textContent = activeCompany;
    document.getElementById("relation-core").textContent = activeCompany;
    document.getElementById("relation-links").innerHTML = links.map(function (text) { return '<div class="relation-chip">' + text + '</div>'; }).join("");
    document.getElementById("chart-subtitle").textContent = activeSeries ? activeSeries.name + ' · 실제 시계열 연결 대기' : '연결할 지표를 선택하면 주가와 함께 표시됩니다';
    document.getElementById("workbench-status").textContent = activeSeries ? activeSeries.name + ' 선택됨' : '지표를 선택해 주세요';
    var legend = document.getElementById("chart-legend");
    legend.style.opacity = activeSeries ? "1" : ".5";
  }
  document.getElementById("open-onboarding").onclick = function () { var box = document.getElementById("onboarding"); box.hidden = !box.hidden; if (!box.hidden) box.scrollIntoView({ behavior: "smooth", block: "nearest" }); };
  document.getElementById("company-apply").onclick = selectCompany;
  document.getElementById("company-search").addEventListener("keydown", function (event) { if (event.key === "Enter") { event.preventDefault(); selectCompany(); } });
  renderCountries(); renderSeries(); renderCompanyOptions(); renderWorkbench();
})();
