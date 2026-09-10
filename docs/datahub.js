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
    taiwan: { label: "대만", code: "TWN", series: [
      ["TSMC 월매출", "월매출 · YoY · 공정 믹스", ["TSMC", "삼성전자", "NVIDIA"]],
      ["반도체 수출", "품목별 수출액 · 단가", ["TSMC", "ASE"]],
      ["패키징·기판", "첨단 패키징 · IC 기판", ["ASE", "TSMC", "삼성전자"]],
      ["서버 ODM", "AI 서버 출하 · 매출", ["NVIDIA", "TSMC"]],
      ["전력·용수", "산업 인프라 사용량", ["TSMC"]]
    ] },
    usa: { label: "미국", code: "USA", series: [
      ["AI 데이터센터 CAPEX", "하이퍼스케일러 투자 · 가이던스", ["NVIDIA", "Amazon", "Microsoft"]],
      ["GPU 임대료", "GPU별 일간 임대 지수", ["NVIDIA", "CoreWeave"]],
      ["클라우드 사용량", "AWS · Azure · GCP 수요", ["Amazon", "Microsoft"]],
      ["AI 서비스 이용자", "MAU · 트래픽 · 구독", ["Microsoft", "NVIDIA"]],
      ["기업 IT 지출", "소프트웨어 · 인프라 지출", ["Microsoft", "Amazon"]]
    ] },
    global: { label: "글로벌", code: "GLB", series: [
      ["DRAM · NAND 가격", "현물 · 계약가격 · 재고", ["삼성전자", "SK하이닉스"]],
      ["해운·운임", "컨테이너 · 항공화물 지수", ["삼성전자", "TSMC"]],
      ["달러·금리", "DXY · 국채금리 · 환율", ["삼성전자", "Amazon", "Microsoft"]],
      ["원자재", "구리 · 유가 · 희토류", ["TSMC", "삼성전자"]],
      ["데이터센터 전력", "전력수요 · 발전설비 · 전력가격", ["NVIDIA", "Amazon", "Microsoft"]]
    ] }
  };
  var COMPANIES = {
    "삼성전자": ["한국 반도체 수출", "메모리 가격", "TSMC 월매출", "DRAM · NAND 가격", "외국인 수급"],
    "SK하이닉스": ["한국 반도체 수출", "메모리 가격", "TSMC 월매출", "DRAM · NAND 가격", "첨단 패키징"],
    "TSMC": ["TSMC 월매출", "대만 반도체 수출", "첨단 패키징", "서버 ODM", "전력·용수"],
    "NVIDIA": ["AI 데이터센터 CAPEX", "GPU 임대료", "TSMC 월매출", "서버 ODM", "데이터센터 전력"],
    "Amazon": ["AI 데이터센터 CAPEX", "클라우드 사용량", "기업 IT 지출", "달러·금리", "데이터센터 전력"],
    "Microsoft": ["AI 데이터센터 CAPEX", "AI 서비스 이용자", "클라우드 사용량", "기업 IT 지출", "달러·금리"]
  };
  var activeCountry = "korea", activeCompany = "삼성전자", activeSeries = null;
  var countryHost = document.getElementById("country-tabs"), seriesHost = document.getElementById("series-grid"), companyHost = document.getElementById("company-tabs");
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
  function renderCompanies() {
    companyHost.innerHTML = Object.keys(COMPANIES).map(function (name) { return '<button class="company-tab' + (name === activeCompany ? ' on' : '') + '" type="button" data-company="' + name + '">' + name + '</button>'; }).join("");
    companyHost.querySelectorAll("button").forEach(function (button) { button.onclick = function () { activeCompany = button.dataset.company; renderCompanies(); renderWorkbench(); }; });
  }
  function renderWorkbench() {
    var links = COMPANIES[activeCompany] || [];
    document.getElementById("chart-company").textContent = activeCompany;
    document.getElementById("relation-core").textContent = activeCompany;
    document.getElementById("relation-links").innerHTML = links.map(function (text) { return '<div class="relation-chip">' + text + '</div>'; }).join("");
    document.getElementById("chart-subtitle").textContent = activeSeries ? activeSeries.name + ' · 실제 시계열 연결 대기' : '연결할 지표를 선택하면 주가와 함께 표시됩니다';
    document.getElementById("workbench-status").textContent = activeSeries ? activeSeries.name + ' 선택됨' : '지표를 선택해 주세요';
    var legend = document.getElementById("chart-legend");
    legend.style.opacity = activeSeries ? "1" : ".5";
  }
  document.getElementById("open-onboarding").onclick = function () { var box = document.getElementById("onboarding"); box.hidden = !box.hidden; if (!box.hidden) box.scrollIntoView({ behavior: "smooth", block: "nearest" }); };
  renderCountries(); renderSeries(); renderCompanies(); renderWorkbench();
})();
