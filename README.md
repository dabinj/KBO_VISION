# KBO_VISION (WIP)

KBO 리그 경기 데이터 및 모든 투구 내용(구종, 위치좌표, 속도)을 Naver Sports API에서 수집하고, 향후 투구에 대해 실시간 예측 모델 구축까지 개발하기 위한 프로젝트다. <br>
(사심으로) 한화와 류현진의 우승을 돕기위한 프로젝트

```text
Powered by Dabin Jeon
```

현재 본 저장소는 아래 범위까지 데이터 기반 분석이 가능한 상태입니다.

- `2024` KBO 정규시즌 전체
- `2025` 시즌 전체 범위 데이터
- `2026-04-08` 기준 최신 일정 및 일부 실시간 데이터

데이터 규모는 아래와 같습니다.

- `2024`: `720`경기, `223,216`개 투구, `291`명 투수
- `2025`: `720`경기, `217,857`개 투구, `281`명 투수
- `2026-04-08` 기준: `50`경기, `16,036`개 투구, `167`명 투수

## 프로젝트 핵심

본 프로젝트는 단순 기록 수집이 아니라, 투구를 `타석`, `이닝`, `경기 전체` 시퀀스로 해석하고 다음 공의 구종과 위치를 예측하는 것을 목표로 합니다.

현재 중점 질문은 아래와 같습니다.

- 특정 투수는 어떤 상황에서 어떤 구종을 선택하는가
- 포수, 배터리 조합, 상대 타자 특성이 볼배합에 얼마나 영향을 주는가
- 타자의 시즌 성적, 약점 존, 초구 스윙 성향이 실제 호출 패턴에 반영되는가
- 초구와 직전 구종, 볼카운트, 주자상황이 다음 공 선택에 어떤 규칙을 만드는가

## 현재 모델 상태

현재까지의 실험을 종합하면, `세부 구종 multiclass를 단번에 맞히는 방식`보다 `baseline prior를 먼저 깔고 상황 피처로 보정하는 방식`이 더 잘 작동합니다.

특히 오늘 정리된 핵심은 아래와 같습니다.

- 네일 `2025` 초구 구종 예측에서 단순 majority baseline은 `0.3684`
- baseline prior를 row-level feature로 붙인 뒤 `xgboost random-forest mode`는 `0.3985`
- 즉 초구 모델은 `baseline 기반 보정 구조`가 실제로 baseline을 넘기기 시작했습니다
- 네일 `2025` 전체 투구 구종 예측에서는 `count_state + prev_pitch_type_pa_1` 조건부 baseline이 `0.3168`
- 전체 투구 학습 모델 중 최고는 `xgboost random-forest mode 0.3109`
- 따라서 전체 투구에서는 아직 `볼카운트 + 직전 구종` 규칙이 가장 강한 설명력을 보입니다

한 줄로 정리하면, 현재 프로젝트는 `baseline을 명시적으로 feature로 넣는 계층형 예측 구조`로 가는 것이 맞다는 판단입니다.

## 오늘 분석 요약

`2026-04-10` 기준 네일 분석에서 확인된 내용은 아래와 같습니다.

- 초구 구종은 `상대팀`, `주자상황`, `아웃카운트`, `포수`, `타자 좌우`, `타자 초구 성향`에 따라 달라집니다
- 다만 `초구 exact pitch type`은 여전히 어려운 문제이고, `초구 위치`는 상대적으로 더 잘 맞습니다
- 네일 초구는 초반 이닝에서 `투심` 중심성이 강하고, 중반 이후 `체인지업`과 다른 변화구가 더 많이 섞입니다
- 한화 상대에서는 특정 타자에게 `체인지업 초구`가 집중된 패턴이 보였습니다
- 전체 투구 모델에서는 `볼카운트`, `직전 구종`, `주자상황`, `이닝`, `포수`가 핵심 축으로 작동합니다

## Example Visuals

### 네일 초구 모델 성능 요약

![Naile First Pitch Model Accuracy Summary](examples/naile_first_pitch_model_accuracy_summary_2025.svg)

### 네일 초구 전체 위치 확률 지도

![Naile First Zone Probability 2025](examples/naile_first_zone_probability_2025.svg)

### 네일 초구 실제 위치 산포도

![Naile First Pitch Scatter 2025](examples/naile_first_pitch_scatter_2025.svg)

### KIA 포수별 초구 스트라이크존 비교

![KIA Catcher First Pitch Zone 2025](examples/kia_catcher_first_pitch_zone_2025.svg)

### KIA 포수별 초구 구종 분포 비교

![KIA Catcher First Pitch Comparison 2025](examples/kia_catcher_first_pitch_comparison_2025.svg)

### 한화 타자 2025 약점 존 요약

![Hanwha Batter Weak Zones 2025](examples/hanwha_batter_weak_zones_2025.svg)

## 매일 갱신할 예측 섹션

README 하단 예측 섹션 제목은 매일 아래 형식으로 최신화합니다.

- `YYYY.MM.DD 선발투수 "이름" 예측`

예시:

- `2026.04.10 선발투수 "네일" 예측`

이 섹션에는 아래 내용을 경기 전 기준으로 계속 업데이트합니다.

- 예상 타순 기준 초구/다음 공 시나리오
- 선발투수의 이닝별 장기 시퀀스 흐름
- 당시까지의 시즌 기록, baseline prior, 포수 영향, 타자 성향을 반영한 예측 보드

## 2026.04.10 선발투수 "네일" 예측

기준: 네일 `2025` 실제 투구 패턴, 포수 영향, 타자 성향, 그리고 baseline prior 기반 시나리오

![Hanwha Tomorrow Fun Board](examples/hanwha_tomorrow_fun_board.svg)

## 주요 스크립트

- [fetch_kbo_schedule.py](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/scripts/fetch_kbo_schedule.py)
- [fetch_kbo_season.py](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/scripts/fetch_kbo_season.py)
- [build_pitch_context_table.py](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/scripts/build_pitch_context_table.py)
- [build_model_tables.py](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/scripts/build_model_tables.py)
- [build_first_pitch_driver_table.py](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/scripts/build_first_pitch_driver_table.py)
- [build_all_pitch_driver_table.py](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/scripts/build_all_pitch_driver_table.py)
- [augment_first_pitch_baseline_priors.py](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/scripts/augment_first_pitch_baseline_priors.py)
- [benchmark_first_pitch_algorithms.py](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/scripts/benchmark_first_pitch_algorithms.py)

## 관련 문서

- [PITCH_SEQUENCE_MODEL_PLAN.md](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/config/PITCH_SEQUENCE_MODEL_PLAN.md)
- [FIRST_PITCH_MODEL_ARCHITECTURE_RECOMMENDATION.md](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/config/FIRST_PITCH_MODEL_ARCHITECTURE_RECOMMENDATION.md)
- [ALGORITHM_SELECTION_POLICY.md](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/config/ALGORITHM_SELECTION_POLICY.md)
- [HANWHA_DAILY_TABLES_PLAN.md](/c:/Users/Dabin%20Jeon/Documents/DevOps/KBO_VISION/config/HANWHA_DAILY_TABLES_PLAN.md)

## 실행 예시

```powershell
python scripts\fetch_kbo_season.py --season-year 2024 --round-code kbo_r --reuse-existing
python scripts\build_first_pitch_driver_table.py --input-csv ... --weakness-csv ... --swing-csv ... --pitcher-team-code HT --output-csv ...
python scripts\benchmark_first_pitch_algorithms.py --input-csv ... --target first_pitch_type --output-json ...
```

## Note

- `data/` 아래 원본 산출물은 대부분 git 추적에서 제외합니다
- 버전 관리는 코드, 문서, 예시 SVG 중심으로 유지합니다
- 현재 모델은 `baseline을 이기는가`를 가장 중요한 평가 기준으로 둡니다
