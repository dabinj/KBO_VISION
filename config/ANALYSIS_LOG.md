# KBO_Sabermatrix Analysis Log

## 2026-04-07 Summary

아래 내용은 현재까지 Naver Sports KBO API를 탐색하면서 확인한 결과를 기록한 것이다.

## 1. Schedule API

사용 API:

`https://api-gw.sports.naver.com/schedule/games?fields=basic,schedule,baseball,manualRelayUrl&upperCategoryId=kbaseball&fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD&size=500`

확인 사항:

- 특정 날짜의 경기 리스트를 가져올 수 있다.
- KBO 외 `kbaseballetc` 같은 항목도 포함되므로 `categoryId == "kbo"` 필터링이 필요하다.
- `gameId`로 이후 relay / game API 호출이 가능하다.

## 2. Relay API

사용 API:

- `.../schedule/games/{game_id}/relay`
- `.../schedule/games/{game_id}/relay?inning=N`

확인 사항:

- 기본 `relay` 호출은 최신 이닝 구간만 내려오는 경우가 있다.
- `?inning=N` 호출로 각 이닝 데이터를 개별 수집할 수 있다.
- 시즌 경기 전체 적재를 위해서는 inning loop 방식이 필요하다.

## 3. Pitch-Level Data

확인된 필드:

- 투수: `currentGameState.pitcher`
- 타자: `currentGameState.batter`
- 구종: `textOptions[].stuff`
- 구속: `textOptions[].speed`
- 투구 이벤트: `textOptions[].text`
- 투구 결과 코드: `pitchResult`
- 투구 추적값: `ptsOptions`

결론:

- 투수/타자/구종/구속/이벤트/물리 좌표를 투구 단위로 테이블화할 수 있다.

## 4. Pitch Location Interpretation

초기 가설:

- `crossPlateY`가 높이일 가능성을 의심했다.

검증 결과:

- `crossPlateY`는 높이가 아니라 고정된 crossing plane 값이다.
- 실제 높이는 `z0`, `vz0`, `az`, `vy0`, `ay`, `y0`를 이용해 계산해야 한다.
- 프로젝트에서는 이 값을 `plate_z`로 저장한다.

실무 결론:

- 모델 입력 좌표는 `cross_plate_x`, `plate_z`를 사용해야 한다.

## 5. Player Mapping

확인 사항:

- `pcode`는 lineup / entry 데이터와 연결된다.
- 같은 relay 응답 안에서 `pitcher_code -> name`, `batter_code -> name` 매핑이 가능하다.

결론:

- 별도 선수 조회 API 없이도 경기 단위 player map을 만들 수 있다.

## 6. Catcher Tracking

초기 상태:

- lineup의 `포수`만 보면 경기 중 교체 시점을 놓친다.

추가 확인:

- relay `playerChange`에 substitution / shift 이벤트가 기록된다.
- 공격 시 대타 / 대주자 교체 후 다음 수비 이닝에서 수비 포지션이 확정된다.

현재 해석 방식:

- 경기 시작 시 수비 포지션 상태를 만든다.
- substitution 발생 시 기존 수비자 제거 및 신규 수비자 배치
- shift 발생 시 `shiftMessage`의 목표 포지션으로 수비 이동
- 투구 row 생성 시 해당 시점의 수비 포수 상태를 읽는다.

검증 사례:

- `20260331KTHH02026`
  - `6회초`: 최재훈
  - `7회초`: 허인서
- `20260329WOHH02026`
  - `8회초`: 최재훈
  - `9회초`: 허인서

## 7. Plate Result Attachment

확인 사항:

- `pitchResult` 자체는 개별 투구 판정이다.
- 타석 결과는 뒤따르는 이벤트 텍스트에 별도로 남는다.
- 예: `박준순 : 삼진 아웃`, `허인서 : 볼넷`

현재 처리:

- 마지막 투구 row에 `plate_result_text`를 붙인다.

결론:

- pitch 단위와 plate appearance 결과를 같은 테이블에서 같이 다룰 수 있다.

## 8. Visualization

현재 구현:

- 타석별 / 전체 스트라이크존 SVG
- 투구 번호 라벨
- 구종별 shape
- 투구 결과별 color
- 이벤트 로그와 plate result 표시

활용 목적:

- 좌표 검증
- 특정 타자 상대 투구 패턴 확인
- 실제 중계와 데이터 일치 여부 검토

## 9. Real-Time Modeling Feasibility

판단:

- 이 API는 경기 중 실시간 갱신될 가능성이 높다.
- 마지막 확정 투구 상태를 기준으로 다음 구종 확률 예측은 가능하다.

필요 요소:

- 실시간 polling
- 새 `ptsPitchId` 감지
- 상태 변수 생성
- 다음 1구 예측 모델

## 10. Open Issues

- 시즌 전체 수집 자동화 미구현
- 경기 누락 / 중단 경기 처리 미구현
- 구종 표준화 사전 미구현
- feature table / model 학습 스크립트 미구현
- 실시간 predictor 미구현
