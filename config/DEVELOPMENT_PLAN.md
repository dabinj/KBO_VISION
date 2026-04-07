# KBO_Sabermatrix Development Plan

## 1. Objective

이 프로젝트의 1차 목표는 Naver Sports KBO API를 기반으로 경기 단위 raw 데이터와 투구 단위 테이블을 안정적으로 적재하는 것이다.

이 프로젝트의 2차 목표는 적재된 투구 데이터를 바탕으로 다음 투구 구종, 존 공략 위치, 투수-포수 배터리 패턴을 예측하는 실시간/오프라인 통계 모델을 구축하는 것이다.

## 2. Current Scope

현재 구현된 범위는 아래와 같다.

- 경기 일정 수집
- 이닝별 relay 수집
- 투구 단위 CSV 생성
- 투수, 타자, 포수 식별자 매핑
- 구종, 구속, 투구 위치 추출
- plate result 이벤트 연결
- 타자 필터 기반 SVG 시각화

## 3. Implemented Functions

### 3.1 Schedule Collection

- 날짜 범위별 KBO 경기 일정 수집
- `categoryId == "kbo"` 필터링
- CSV / JSON 저장

### 3.2 Relay Collection

- 단일 경기 `game_id` 대상 relay 호출
- `?inning=N` 방식으로 1회~마지막 이닝까지 수집
- 이닝별 raw payload 저장

### 3.3 Pitch Table Extraction

- `ptsOptions` 기반 pitch row 생성
- `pitcher_code`, `batter_code`, `catcher_code` 저장
- `pitcher_name`, `batter_name`, `catcher_name` 매핑
- `pitch_type`, `speed`, `pitch_result`, `event_text` 저장
- `plate_result_text`, `plate_result_type`를 마지막 투구에 연결

### 3.4 Catcher Tracking

- 시작 라인업 기반 수비 포지션 상태 초기화
- `playerChange.substitution` 처리
- `playerChange.shift` 처리
- 공격 중 대타/대주자 교체 후 다음 수비 이닝 배치 추적
- 현재는 포수뿐 아니라 전체 수비 포지션 상태를 관리하는 구조

### 3.5 Pitch Location Visualization

- 스트라이크존 SVG 생성
- 타석별 투구 번호 표기
- 구종별 shape 분리
- 투구 결과별 색상 분리
- 하단 이벤트 로그 출력

## 4. Next Development Tasks

### 4.1 Data Pipeline

- 시즌 범위 자동 수집 스크립트 추가
- 경기 리스트 -> raw relay -> pitch table 일괄 적재
- 중복 적재 방지 로직 추가
- 실패 경기 재시도 로직 추가

### 4.2 Data Model

- `games` 테이블
- `players` 테이블
- `pitch_events` 테이블
- `plate_appearances` 테이블
- `defensive_state` 또는 `battery_state` 테이블

### 4.3 Derived Features

- zone in/out
- 9분할 zone
- 구종 대분류
- count state
- runner state
- 직전 1~3구 sequence
- batter handedness / pitcher handedness
- pitcher-catcher battery features

### 4.4 Modeling

- baseline: 직구 vs 비직구
- multiclass: 직구/슬라이더/포크/커브/기타
- location model: high/low, inside/outside
- 실시간 inference용 polling 기반 predictor

### 4.5 Validation

- 수기 중계 화면과 API 좌표 비교
- 포수 교체 시점 검증
- plate result 연결 검증
- 경기 단위 누락 투구 확인

## 5. Risks

- relay 응답 구조가 시즌 중 변경될 수 있음
- 실시간 API 반영 지연이 있을 수 있음
- `playerChange` 이벤트 표현 방식이 경기마다 조금 다를 수 있음
- 구종 명칭 표준화가 필요함

## 6. Recommended Immediate Order

1. 시즌 단위 수집 스크립트 작성
2. 적재 포맷 고정
3. 파생 변수 생성
4. 오프라인 예측 모델 baseline 구축
5. 실시간 polling / inference 모듈 추가
