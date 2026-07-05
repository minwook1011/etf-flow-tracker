# etf-flow-tracker — 글로벌 섹터 자금흐름 + 세상 흐름 트래커

정적 대시보드 4페이지 + 표준 라이브러리 전용 파이썬 파이프라인 + GitHub Actions 자동 갱신.
API 키·pip 의존성·빌드 도구 없음. GitHub Pages(`docs/`)로 서빙.

## 페이지 구성

| 페이지 | 내용 | 데이터 소스 |
|---|---|---|
| `index.html` 섹터 대시보드 | 기간별 수익률 바차트, 누적 트렌드, 그룹 히트맵(자금유입 배지), 전 종목 테이블, 종목 모달(캔들+구성종목+뉴스) | `data.json` (자동) |
| `megacap.html` 글로벌 메가캡 | TOP100/300 토글, 13개 섹터 강세 순위(중앙값), 섹터별 종목 카드(선행PER), 종목 모달(캔들+회사개요+뉴스) | `megacap.json` (자동), `megacap_profiles.json` (반자동 — 회사 개요) |
| `perspective.html` 핵심 테제 트래킹 | 주차 탭, 테제별 종목 카드+관련 ETF 자동매칭, 등록일 이후 평균 수익률(테제 스코어) | `theses.json` (수동) + `data.json`/`megacap.json`의 시세 |
| `worldflow.html` 세상 흐름 파악 | [주요 일정] 월별 캘린더·다가오는 행사·행사 모달 / [핵심 인력] 키워드 검색·인물 디렉토리·주차별 발언 | `events.json`, `people.json` (반자동) |

## 로컬 실행법

```bash
# 1) 데이터 생성 (표준 라이브러리만 사용, 파이썬 3.10+)
python fetch_data.py        # 섹터 ETF 시세+뉴스 → docs/data.json (약 3분)
python fetch_universe.py    # 시총 TOP300 명단 → docs/megacap_universe.json (약 4분, 주 1회면 충분)
python fetch_megacap.py     # 명단 시세+PER+캔들+뉴스 갱신 → docs/megacap.json (약 10~15분, 300종 뉴스 수집 포함)

# 2) 로컬 서버
python -m http.server 8000 -d docs
# → http://localhost:8000
```

## 수정 지점

- **추적 ETF 추가/삭제**: `fetch_data.py` 상단 `TICKERS` (티커, 한글명, 그룹, 뉴스검색어)
- **ETF 대표 구성종목**: `fetch_data.py`의 `CONSTITUENTS`
- **메가캡 후보군/섹터 분류**: `fetch_universe.py`의 `CANDIDATES` (13개 섹터 수동 분류)
- **테제 등록**: `docs/theses.json` — 주차 섹션에 `{title, summary, tickers(미국), kr(한국 코드.KS/.KQ)}` 추가. 티커 시세는 다음 `fetch_data.py` 실행 때 자동 수집됨
- **행사 등록/갱신**: `docs/events.json` — `status`: `upcoming`(예정) → `previewed`(발표 내용 공개, `preview` 채움) → `done`(종료, `summary`/`full` 작성)
- **인물/발언 등록**: `docs/people.json` — `people`에 인물(`type`: tech/investor/policy/corp), `weeks[].statements`에 발언(요약+시사점, 파급 크면 `analysis` 마크다운). `added`가 4일 이내면 NEW 배지
- **메가캡 회사 개요 추가/보완**: `docs/megacap_profiles.json` — `profiles.{TICKER}.biz`에 "무엇을 하는 회사인지" 한 줄. **자동 갱신 대상이 아님** — `fetch_universe.py`가 주 1회 TOP300 명단을 재산정하면서 새 종목이 편입될 수 있는데, 이 파일은 그때 자동으로 채워지지 않는다. `fetch_megacap.py` 실행 로그에 `[안내] megacap_profiles.json에 회사개요 없는 신규 종목 N개: ...`가 뜨면 해당 티커의 개요를 채워 넣을 것 (모달은 개요가 없어도 "준비되지 않았습니다" 안내만 뜨고 깨지지는 않음)

## 일일 운영법

- **자동 (건드릴 것 없음)**: 평일 한국시간 오후 8:00에 `update.yml`이 `data.json`/`megacap.json` 갱신·커밋. 일요일 밤 `universe.yml`이 TOP300 명단 재산정. 두 워크플로는 `theses/events/people.json`을 절대 건드리지 않음
- **3일 주기 (수동, 클로드 코드)**: repo 폴더에서 `claude` 실행 후 "세상 흐름 파악 업데이트" 프롬프트로 최근 발언·행사 preview/summary 갱신 → 커밋·푸시
- **수시**: 새 테제가 생기면 `theses.json`에 추가 (다음 자동 갱신 때 스코어 계산 시작)
- 인용 규칙: 인물 발언·기사는 반드시 요약 저장, 직접 인용은 15단어 미만, 출처 링크 필수

## 데이터 계약 (필드 요약)

- `data.json` — `etfs.{TICKER}`: `r1d/r1w/r1m/r3m/ytd`(수익률), `rel_*`(ACWI 대비 초과수익), `vol_ratio`(5일/20일 평균 거래대금 = 자금유입 프록시), `from_high`(52주 고점 대비 %), `spark/hist/candles/holdings/news`, 그리고 `thesis_quotes`(테제 티커 6개월 종가 시계열)
- `megacap.json` — `stocks[]`: `ticker/name/sector/rank/mcap_usd/price/r1w/r1m/r3m/ytd/from_high/vol_ratio/pe_now/pe_next/spark/candles/news`
- `megacap_profiles.json` — `profiles.{TICKER}.biz`: 회사 개요 한 줄 (반자동, 위 "수정 지점" 참조)
- `events.json` / `people.json` / `theses.json` — 스키마는 각 파일 참조 (필드명 유지 필수)

## 안전장치

- 모든 외부 요청: User-Agent 명시, 요청 간 0.5초 이상, 3회 재시도 후 스킵
- `fetch_data.py`: 티커 80% 이상 실패 시 기존 `data.json` 유지 후 종료
- `fetch_universe.py`: 크럼 확보 실패·성공 종목 과소 시 기존 명단 유지
- 프론트: JSON 로드 실패 시에도 페이지가 깨지지 않고 안내 문구 표시
