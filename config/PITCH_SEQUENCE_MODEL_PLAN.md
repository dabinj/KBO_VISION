# Pitch Sequence Prediction Plan

## 1. Goal

2024 KBO pitch-level data를 바탕으로 다음 투구의 구종 선택을 예측하는 모델을 설계한다.

핵심 목표는 단순 구종 분류를 넘어서, 투구가 발생하는 문맥을 `시퀀스`로 해석하는 것이다.

우리가 다루려는 시퀀스는 세 가지다.

- 단기 시퀀스: 한 타석의 초구부터 마지막 투구까지
- 중간 시퀀스: 한 이닝 안에서 이어지는 투구 흐름
- 장기 시퀀스: 경기 전체에서 누적되는 배합 흐름

이 문서의 목적은 모델링 전에 문제 정의, 데이터 설계, 피처 설계, 학습 전략, 평가 전략을 정교하게 고정하는 것이다.

## 2. What We Predict

### 2.1 Primary target

가장 먼저 예측할 타깃은 `다음 투구의 구종`이다.

후보 방식:

- coarse class: 직구 / 슬라이더계 / 커브계 / 포크-체인지업계 / 기타
- fine class: API 원본 `pitch_type` 기준 multiclass

권장 순서:

1. coarse class baseline
2. fine class multiclass
3. 필요하면 연속형 위치 예측 모델 분리

### 2.2 Optional secondary targets

추후 확장 가능한 타깃:

- 다음 투구의 존 내외
- high / middle / low
- inside / middle / outside
- 승부구 여부
- 결정구 여부

하지만 1차 목표는 반드시 `구종 선택`에 집중한다.

## 3. Core Modeling Question

우리가 실제로 풀고 싶은 질문은 아래와 같다.

`현재 경기 상태와 직전 시퀀스를 알고 있을 때, 이번 투수-포수-벤치 조합은 다음 공으로 무엇을 선택할 가능성이 높은가?`

즉 이 문제는 단순 pitch classification이 아니라:

- 상태 기반 의사결정 문제
- 다중 시계열 문맥 문제
- batter / pitcher / catcher / game-state 상호작용 문제

로 봐야 한다.

## 4. Sequence Definition

### 4.1 Short sequence: plate appearance level

정의:

- 같은 타석 안에서의 pitch order
- 시작은 초구
- 종료는 plate appearance 종료 시점

중요 정보:

- 같은 타자 상대로 직전 1~N구 조합
- 현재 볼카운트
- 파울, 헛스윙, 볼, 인플레이 누적 흐름
- 같은 타석 내에서 이미 보여준 구종 diversity
- 타석 내 pitch tunneling / setup pitch / finish pitch 관계

핵심 가설:

- 다음 구종 선택은 가장 직접적으로 타석 내부 시퀀스의 영향을 받는다.

### 4.2 Mid sequence: inning level

정의:

- 같은 이닝에서 누적된 모든 pitch 흐름
- 타석이 바뀌어도 이어지는 문맥

중요 정보:

- 이닝 시작 이후 총 투구수
- 이닝 내 실점, 출루, 아웃카운트 변화
- 같은 이닝 내 타순 순환
- 방금 전 타석 결과
- 위기 상황에서의 배합 변화

핵심 가설:

- 투수는 같은 이닝 안에서 체력, 제구, 위기 정도에 따라 구종 mix를 바꾼다.

### 4.3 Long sequence: game level

정의:

- 경기 시작 이후 현재 투구 시점까지의 누적 흐름

중요 정보:

- 경기 누적 투구수
- 투수의 times-through-order
- 경기 전체 score leverage
- 특정 타자 상대 과거 배합
- 경기 초중후반의 운영 전략 차이

핵심 가설:

- 경기 전체 흐름은 short sequence보다 느리지만, 전체 구종 mix의 prior를 결정한다.

## 5. Prediction Unit

모델의 샘플 단위는 `투구 1개`로 한다.

각 row는 아래를 포함해야 한다.

- 시점 t 직전까지 관측 가능한 정보만 feature에 포함
- label은 시점 t의 실제 구종
- 미래 정보 누설 금지

즉 모든 feature는 반드시 `다음 공이 던져지기 직전` 기준으로 계산되어야 한다.

## 6. Candidate Features

### 6.1 Static identity features

- pitcher_id
- batter_id
- catcher_id
- pitching team
- batting team
- pitcher handedness
- batter handedness
- pitcher role: starter / reliever

### 6.2 Game-state features

- inning
- top / bottom
- outs
- balls
- strikes
- base state
- score differential
- home / away
- winning / tied / trailing
- leverage proxy

### 6.3 Pitcher workload features

- game pitch count
- inning pitch count
- plate appearance pitch count
- days rest if available later
- times through order
- this batter faced count in game

### 6.4 Sequence summary features

- previous pitch type
- previous 2~5 pitch types
- previous pitch results
- previous plate result
- same batter previous encounter in game
- same inning pitch-type distribution
- game-level pitch-type distribution so far

### 6.5 Interaction features

- pitcher x catcher
- pitcher x batter
- pitcher x count
- pitcher x runner_state
- catcher x count
- score_diff x inning
- batter handedness x pitch location history

### 6.6 Decision-maker proxy features

사용자가 강조한 핵심은 `누가 볼배합을 하느냐`이다.

직접 관측은 어렵지만 아래 proxy를 만들 수 있다.

- catcher_id
- pitcher-catcher battery pair id
- pitcher baseline mix
- catcher baseline received mix
- battery-specific deviation from pitcher baseline
- high leverage 여부
- runner in scoring position 여부
- mound visit / change 직후 여부가 나중에 확보되면 추가

실무적으로는 `누가 결정했는지`를 직접 맞히기보다, `배합 결정권의 흔적`을 반영하는 latent context로 접근하는 편이 더 현실적이다.

## 7. Proposed Data Tables

### 7.1 pitch_model_table

가장 중요한 학습용 마스터 테이블.

각 row는 다음 정보를 포함한다.

- game_id
- inning / half / plate appearance id
- pitch_index_in_pa
- pitch_index_in_inning
- pitch_index_in_game
- pitcher / batter / catcher ids
- state features
- sequence features
- target_pitch_type

### 7.2 plate_appearance_table

- 타석 시작 상태
- 타석 종료 결과
- 타석 길이
- 타석 내 구종 분포

### 7.3 inning_context_table

- 이닝 시작 시점
- 이닝 누적 실점
- 이닝 누적 투구수
- 이닝 내 타자 수

### 7.4 game_context_table

- 경기 누적 pitch mix
- pitcher fatigue proxy
- lineup turn information

## 8. Modeling Strategy

### 8.1 Stage 1: strong tabular baseline

추천 모델:

- LightGBM
- CatBoost

목적:

- feature importance 확인
- 누설 여부 점검
- 베이스라인 성능 확보

장점:

- 빠른 학습
- 해석 용이
- sparse categorical + numeric 혼합에 강함

### 8.2 Stage 2: hierarchical sequence model

추천 구조:

- short encoder + mid encoder + long encoder
- 최종 fusion layer로 다음 구종 예측

후보 모델:

- GRU / LSTM with three context windows
- Transformer encoder with segmented sequence inputs

권장 설계:

- short context: 최근 타석 pitch sequence
- mid context: 현재 이닝 sequence summary
- long context: 경기 전체 recent summary
- static/context tabular features는 별도 branch로 병합

### 8.3 Stage 3: mixed architecture

가장 현실적인 최종 형태 제안:

- tabular model 1개
- sequence model 1개
- 둘의 soft voting 또는 stacking

이유:

- tabular은 안정적 baseline 제공
- sequence model은 흐름 정보 포착
- 둘을 합치면 성능과 해석력 균형이 좋다

## 9. Recommended Initial Targets

처음부터 너무 많은 클래스를 바로 맞히려 하지 않는 것이 좋다.

우선순위:

1. next coarse pitch type
2. next fine pitch type
3. next pitch location bucket

이 순서가 좋은 이유:

- coarse target에서 시퀀스 구조가 실제로 먹히는지 먼저 확인 가능
- fine target은 데이터 희소성과 클래스 불균형 문제를 더 크게 받음

## 10. Train / Validation Split

무작위 split은 금지하는 것이 좋다.

권장 split:

- time-based split
- season chronological split
- 예: 3~7월 train, 8월 validation, 9~10월 test

추가 평가:

- unseen game split
- unseen battery pair split
- pitcher-specific holdout

이유:

- 실제 운영은 미래 경기 예측이므로 시간 누설을 막아야 함

## 11. Metrics

필수 metric:

- top-1 accuracy
- top-3 accuracy
- macro F1
- log loss

추가 분석:

- count state별 성능
- runner state별 성능
- pitcher별 성능
- catcher별 성능
- 고 leverage 상황 성능

실전 관점에서는 top-3 accuracy가 특히 중요할 수 있다.

## 12. Explainability

모델이 좋아도 현업 해석이 안 되면 활용성이 떨어진다.

권장:

- SHAP for tabular baseline
- state bucket별 confusion matrix
- count / runner / score_diff 조건별 predicted mix 비교
- pitcher별 실제 mix vs 예측 mix 비교

## 13. Key Risks

### 13.1 Label noise

- pitch_type 표기 일관성 문제
- coarse mapping 기준 필요

### 13.2 Decision-maker ambiguity

- 실제 호출 주체를 직접 관측할 수 없음
- catcher_id와 battery context는 proxy일 뿐

### 13.3 Data leakage

- plate result, 미래 outcome, 종료 후 누적값이 feature에 들어가면 안 됨

### 13.4 Sparsity

- 특정 battery pair나 희귀 구종은 표본이 적음

## 14. Recommended Build Order

### Phase 1. Data definition

- pitch_model_table 스키마 고정
- coarse pitch mapping 사전 정의
- plate appearance id / inning sequence id / game sequence id 생성

### Phase 2. Baseline features

- count, runner, score_diff, pitch_count, prev_pitch_type
- pitcher / batter / catcher categorical
- short / mid / long sequence summary feature 생성

### Phase 3. Baseline model

- LightGBM multiclass baseline
- feature importance와 오류 케이스 분석

### Phase 4. Sequence model

- short-only 모델
- short + mid 모델
- short + mid + long 모델

각 단계에서 incremental gain을 확인한다.

### Phase 5. Decision-maker modeling

- catcher / battery features 강화
- pitcher baseline vs catcher-shift 효과 분석
- 상황별 배합 주도권 proxy 실험

## 15. My Recommendation

현재 단계에서 가장 좋은 출발점은 아래다.

1. `다음 구종`을 coarse class로 예측한다.
2. 샘플 단위는 `투구 1개`로 둔다.
3. short / mid / long sequence를 모두 별도 피처 그룹으로 만든다.
4. 첫 모델은 LightGBM으로 시작한다.
5. 이후에만 sequence neural model로 확장한다.

특히 사용자가 말한 핵심 아이디어 중 가장 강한 부분은 `투구는 독립 사건이 아니라 다층 시퀀스`라는 점이다.
이 철학은 아주 좋고, 실제 성능 차이도 여기서 날 가능성이 높다.

다만 첫 구현은 반드시:

- 강한 baseline
- 엄격한 시간 분리
- 누설 방지
- coarse target

로 시작해야 한다.

## 16. Immediate Next Document

이 문서 다음으로 바로 필요한 것은 `feature specification` 문서다.

다음 단계에서 작성할 문서 제안:

- `config/FEATURE_SPEC_PITCH_SEQUENCE.md`

이 문서에는 각 feature의:

- 정의
- 계산 시점
- source column
- 누설 위험
- 결측 처리

를 한 줄씩 명시하는 것이 좋다.

## 17. Long-Term Weakness And Short-Term Form Blend

타자 약점 정보는 한 시점의 정적 값으로만 보면 부족하다.

권장 구조는 아래 두 축을 함께 쓰는 것이다.

- 장기 약점: 2024 시즌 고정 프로파일
- 단기 상태: 2025 현재 시점 직전까지의 누적 성적

### 17.1 Why this blend is needed

2024 약점 프로파일은 타자의 구조적 성향을 설명한다.

예:

- 몸쪽 약점
- 바깥쪽 약점
- 높은 코스 약점
- 낮은 코스 약점
- 특정 구종 약점
- 특정 `구종 x 존` 조합 약점

하지만 시즌이 바뀌면 타자는 보완할 수 있고, 시즌 중반 이후에는 당해연도 컨디션과 수정된 스윙 패턴이 더 중요해질 수 있다.

즉 모델은:

- 시즌 초반에는 2024 장기 약점에 더 의존
- 시즌 중반 이후에는 2025 단기 상태를 더 강하게 반영

하는 구조가 바람직하다.

### 17.2 Recommended time-weighting idea

단순하고 실용적인 권장안:

- 2025 시즌 초반: `2024 profile` 비중 높음
- 2025 시즌 중반: `2024 profile`과 `2025 live stats` 혼합
- 2025 시즌 후반: `2025 live stats` 비중 높음

예시 개념:

- `batter_weakness_long_term_score`
- `batter_weakness_short_term_score`
- `season_progress_ratio`
- `blended_weakness_score = (1 - w) * long_term + w * short_term`

여기서 `w`는 시즌 진행률 또는 누적 타석 수에 따라 증가한다.

### 17.3 Better weighting key than calendar alone

달력 날짜보다 더 좋은 기준은 타자의 누적 타석 수다.

권장:

- `batter_2025_pa_before_pitch`
- 이 값을 기준으로 short-term 신뢰도를 조절

예:

- 타석 수가 적으면 2024 약점 비중 유지
- 타석 수가 충분히 쌓이면 2025 실시간 약점 비중 확대

### 17.4 Recommended implementation order

1. 2024 타자 약점 프로파일 테이블 생성
2. 2025 시점 직전 타자 라이브 성적 테이블 생성
3. 두 값을 혼합한 blended weakness feature 생성
4. 화이트 / 포수 모델에 순차적으로 투입해 성능 비교

### 17.5 Practical conclusion

결론적으로 타자 약점은 아래처럼 쓰는 것이 가장 좋다.

- 고정 prior: 2024 시즌 약점 프로파일
- 업데이트 signal: 2025 현재 시점 직전 성적
- 가중 방식: 시즌 진행 또는 누적 타석 수 기반 blend

이 구조가 가장 야구적으로도 자연스럽고, 누설 없이 운영 가능한 형태다.
