# 발표 일정과 수집 정책

조사일 2026-09-12. 모두 한국 시간(UTC+9). 공식 발표시각과 우리가 확인하는 주기를 구별한다.

| 자료 | 원출처 발표 | 실행 정책 | 현재 연결 상태 |
|---|---|---|---|
| 파인엠텍 일별 주가·확정 실적 | 주가는 거래일 일봉. 재무 API의 정확한 반영 시간 미공개 | 24시간 10분 간격 | 실제 수신 |
| 베트남 납품 거래 | 공급자·제공 지연 미확인 | 피드 연결 시 파인엠텍과 같은 확인 주기 | 원본·검증 규칙 필요 |
| DRAM 칩 현물 | 일반 세션 12:00 / 15:40 / 19:10 | 세션부터 20분간 5분 간격 | 자동수집·공개 재배포 허용 확인 대기 |
| DRAM 모듈·NAND 현물 | 해당 공개표 별도 고정 주기 미확인 | 일반 세션 창에 변경 확인 | 동일 |
| DRAM·NAND 계약가격 | 월 1회 원칙, 정확한 일시 미확인 | 일반 세션 창에 공개표 변경 확인 | 동일 |
| 한국 DRAM·플래시 수출 | 매월 15일경, 정확한 시각 미공시 | 15~18일 00:02~23:57 5분 간격, 매일 08:07 과거 정정 조회 | 무료 API 키 필요 |

GitHub 예약 실행은 시각 보장이 없으며 바쁜 시간대에는 지연·누락될 수 있다. 사이트 게시에도 추가 시간이 든다. 실시간 SLA가 필요한 경우 공급자가 허용하는 스트리밍/웹훅 및 상주 수집 서비스가 별도로 필요하다. 새로고침은 최신 **게시 JSON**을 가져오며 외부 수집기를 직접 실행하지 않는다.

## 활성화 설정

- 메모리: 공급자가 자동수집과 공개 재배포를 허용하는지 확인한 후 저장소 **변수** `MEMORY_PRICE_COLLECTION_ALLOWED=true`. 현재 미설정이며 수집 작업은 실행하지 않는다. 공개 숫자 없이 지표명·기준일·연결 대기 상태만 제공한다. TRASS 유료 이용권은 이 가격 공급자의 허가와 별개다.
- 수출: 공공데이터포털에서 해당 API 활용신청 후 저장소 **Secret** `KCS_API_KEY`, **변수** `KCS_EXPORTS_ENABLED=true`. 브라우저·공개 JSON·코드에 인증키를 넣지 않는다. 실제 인증 응답은 키 설정 후 검증해야 한다.
- 베트남: [README.md](README.md)의 검증 피드 계약과 `finemtec_trade_rules.json` 조건을 먼저 충족해야 한다. 세관 신고일은 데이터 공급일이 아니다. 공급자의 실제 배포 일정을 확인하면 확인 창을 다시 조정한다.

같은 데이터를 반복 확인할 때 불필요한 배포를 하지 않는다. 값·기준일·상태가 바뀌면 저장하고 마지막 정상 관측은 수집 실패에도 유지한다. `source_updated_at`이 없는 수출 API에는 null을 남기며 수집 시각을 원출처 발표시각으로 치환하지 않는다.

`publish_pages.py`는 데이터 변경이 없는 실행에서도 최신 Pages 빌드와 main을 비교한다. 이미 게시되었으면 생략하고, 빌드 중이면 요청을 합치며, 커밋 후 배포 요청만 실패한 경우 다음 실행에서 복구한다. 완성된 최신 배포 확인은 Pages 빌드 결과로 판단하며 단순 커밋 성공과 구별한다.

원문 기준일은 수신일보다 오래될 수 있다. 메모리 공개표 조사 결과 DRAM 칩 2026-09-11, 모듈·NAND 2026-08-31, 계약표 2026-07-31이었다. 이 날짜는 매일 최신인 것처럼 바꾸지 않는다.

## 공식 근거

- [DRAMeXchange 일반회원 상세 세션표 및 계약가격 주기](https://www.dramexchange.com/service/faqs)
- [TrendForce 이용 조건](https://www.trendforce.com/about/terms)
- [관세청 품목별 수출입실적(GW)](https://www.data.go.kr/data/15101609/openapi.do)
- [GitHub 예약 실행 지연 안내](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GITHUB_TOKEN 자동 커밋과 Pages 빌드](https://docs.github.com/en/actions/concepts/security/github_token)
- [Pages build 요청](https://docs.github.com/en/rest/pages/pages#request-a-github-pages-build)
