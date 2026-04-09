# First Pitch Model Architecture Recommendation

## 1. Summary

현재까지의 실험 결과를 기준으로 보면, `초구 세부 구종 7종 multiclass`를 한 번에 맞히는 방식은 아직 안정적이지 않습니다.

관찰된 핵심은 다음과 같습니다.

- `majority baseline`이 매우 강하다.
  - 네일 2025 전체 초구에서는 `투심` majority baseline이 `36.84%`
  - 한화 matchup만 보면 `체인지업` majority baseline이 `42.86%`
- 직접 `7구종 multiclass` 예측은 baseline을 일관되게 넘지 못했다.
- 반면 `초구 위치` 예측은 `Top-1 45%대`까지 올라간다.
- `속구계 vs 변화구계`와 같은 상위 계열 분류는 `Top-1 54%대`로 올라간다.

따라서 권장 구조는 다음과 같다.

1. `direct 7-class`를 최종 목표로 두되, 실전 모델의 첫 단계는 아님
2. 먼저 `pitch family`, `location`, `broad intent`를 예측
3. 그 후 세부 구종을 조건부로 좁히는 `hierarchical / staged model` 사용
4. 모델 입력은 `현재 상태 + 장기 prior + 단기 live form + batter weakness + first-pitch tendency`를 모두 포함

## 2. Why Current Direct Multiclass Struggles

초구 세부 구종 multiclass가 어려운 이유는 다음과 같다.

- 초구 자체가 투수의 강한 prior를 갖는다.
  - 네일은 특정 구종(`투심`)의 기본 사용 비율이 높다.
- class 수가 많고 표본이 제한적이다.
  - `664`개 초구로 `7`개 세부 구종을 안정적으로 분리하기 어렵다.
- 일부 feature는 신호가 있어도 class-level uncertainty를 완전히 분리하지 못한다.
- matchup, inning, catcher, batter weakness가 모두 작용하므로 경계가 복잡하다.

즉 현재 문제는 “피처가 전혀 없다”가 아니라 “세부 구종까지 한 번에 분리하기엔 data regime이 아직 작다”에 더 가깝다.

## 3. Recommended Targets

### 3.1 Stage A: high-value coarse targets

먼저 아래 target을 안정적으로 맞히는 것이 우선이다.

- `pitch_family`
  - FASTBALL vs BREAKING
- `two-seam vs non-two-seam`
  - 네일처럼 특정 primary pitch가 강한 투수에게 특히 중요
- `location_zone`
  - `9-zone + OUT`
- `zone_side_rel`
  - INSIDE / MIDDLE / OUTSIDE / OUT
- `zone_height_rel`
  - HIGH / MIDDLE / LOW / OUT

### 3.2 Stage B: conditional targets

Stage A 결과를 바탕으로 세부 구종을 예측한다.

- if `FASTBALL`:
  - `직구 / 투심 / 커터`
- if `BREAKING`:
  - `체인지업 / 슬라이더 / 스위퍼 / 커브 / 포크`

이렇게 하면 표본이 분산되는 문제가 줄고, 투수의 실제 의사결정 흐름에도 더 가깝다.

### 3.3 Stage C: joint practical output

실전에서 필요한 최종 출력은 아래다.

- `P(pitch_family)`
- `P(pitch_type | family)`
- `P(zone | current state)`
- optional: `P(zone | pitch_type, current state)`

실전용 해석은 최종적으로 아래 형태가 좋다.

- `투심 + 바깥쪽 낮게 22%`
- `체인지업 + 존 밖 낮게 18%`
- `커터 + 높은 몸쪽 11%`

## 4. Recommended Training Tables

### 4.1 master_pitch_table

모든 pitch의 학습 마스터 테이블.

필수 컬럼:

- identifiers
  - `game_id`
  - `pitcher_code`
  - `catcher_code`
  - `batter_code`
  - `team/opponent_team_code`
- state
  - `inning`
  - `half`
  - `outs`
  - `runner_state`
  - `runners_on`
  - `score_diff_pitcher`
  - `count_state`
- sequence
  - `pitch_index_in_pa`
  - `pitch_index_in_inning`
  - `pitch_index_in_game`
  - `prev_pitch_type_pa_1~3`
  - `prev_zone_9_pa_1`
  - `prev_pitch_type_inning_1`
  - `prev_pitch_type_game_1`
- targets
  - `pitch_type`
  - `pitch_family`
  - `zone_9`
  - `zone_side_rel`
  - `zone_height_rel`

### 4.2 first_pitch_table

초구 전용 모델은 별도 테이블로 두는 것이 맞다.

필수 컬럼:

- `count_state = 0-0`
- `runner_state`
- `outs`
- `inning`
- `pitcher/catcher/batter ids`
- `opponent_team_code`
- `first_pitch_type`
- `first_pitch_family`
- `first_zone_9`
- `first_zone_side_rel`

초구는 타석 시퀀스가 아니라 “초기 선택” 문제이므로, 별도 분리하는 편이 훨씬 해석과 실험이 쉽다.

### 4.3 next_pitch_table

2구 이후 모델을 위해 별도 테이블 유지.

필수 컬럼:

- `current_pitch_type`
- `current_zone_9`
- `current_result`
- `next_pitch_type`
- `next_zone_9`

## 5. Feature Groups That Should Be Added

현재 feature set은 꽤 좋아졌지만, 실제로 더 넣어야 하는 고가치 feature가 남아 있다.

### 5.1 Batter season performance features

현재는 주로 `BA` 위주다. 이것만으로는 부족하다.

반드시 추가할 것:

- `season_obp_before_pitch`
- `season_slg_before_pitch`
- `season_ops_before_pitch`
- `season_iso_before_pitch`
- `season_bb_rate_before_pitch`
- `season_k_rate_before_pitch`
- `season_contact_rate_before_pitch` if derivable
- `season_inplay_hit_rate_before_pitch`

이유:

- 타율 하나로는 타자 성향을 설명하기 어렵다.
- 출루형 / 장타형 / 컨택형 / 삼진형 타자는 초구 대응과 투수의 초구 전략이 다르다.

### 5.2 Split performance features

- `vs_rhp_ba_before_pitch`, `vs_lhp_ba_before_pitch`
- `vs_rhp_ops_before_pitch`, `vs_lhp_ops_before_pitch`
- `vs_fastball_family_perf_before_pitch`
- `vs_breaking_family_perf_before_pitch`
- `vs_two_seam_perf_before_pitch`
- `vs_changeup_perf_before_pitch`

이유:

- 초구는 투수-타자 handedness와 구종 대응력이 강하게 작동하는 구간이다.

### 5.3 Count / first-pitch behavior features

이미 초구 스윙 성향은 추가했지만 더 확장할 수 있다.

- `first_pitch_swing_rate`
- `first_pitch_in_zone_swing_rate`
- `first_pitch_out_zone_swing_rate`
- `first_pitch_take_strike_rate`
- `first_pitch_ball_take_rate`
- `first_pitch_whiff_rate`
- `first_pitch_inplay_rate`
- `first_pitch_hard_contact_rate` if derivable later

### 5.4 Batter weakness profile features

현재 2024 약점 profile은 좋은 방향이다. 다만 더 정교화가 필요하다.

- `weak_zone_prior`
- `weak_side_prior`
- `weak_height_prior`
- `weak_pitch_family_prior`
- `weak_specific_pitch_prior`
- `zone x pitch_family weakness`
- `zone x pitch_type weakness`

또한 다음 원칙을 따른다.

- previous season sample exists:
  - `previous season prior + current season live`
- previous season sample missing:
  - `current season live only`
- both sparse:
  - `league/handedness fallback`

### 5.5 Catcher / battery features

- `catcher_name`
- `pitcher_catcher_pair_id`
- `catcher_first_pitch_mix_prior`
- `battery_first_pitch_mix_prior`
- `catcher_zone_preference_prior`
- `catcher_with_pitcher_delta`

이유:

- 현재 실험에서 `catcher_name`은 초구 위치와 일부 구종에 매우 강한 신호로 나타남

### 5.6 Workload / progression features

- `inning`
- `times_through_order`
- `game_pitch_count_before_pitch`
- `inning_pitch_count_before_pitch`
- `pitcher_faced_batter_times_in_game`
- `days_rest` if available later

이유:

- 네일 실험에서 1회와 5~6회 초구 mix가 실제로 달라졌다.

## 6. Recommended Model Stack

### 6.1 Baseline stack

- Majority baseline
- Conditional majority baseline
  - by catcher
  - by opponent
  - by count/runner state

이건 반드시 같이 유지해야 한다.

### 6.2 Practical production stack

- Model A: `pitch_family`
  - XGBoost / LightGBM
- Model B: `primary pitch gate`
  - example: `투심 vs non-투심`
- Model C: `zone_9`
  - XGBoost / LightGBM
- Model D: `pitch_type within family`
  - family-conditioned classifier

권장 출력 결합:

- `family_prob`
- `primary_gate_prob`
- `zone_prob`
- `type_given_family_prob`

### 6.3 Not recommended yet

- direct `7-class first-pitch multiclass` as main production model

이건 계속 실험은 가능하지만, 현재는 baseline superiority가 확인되지 않았다.

## 7. Evaluation Rules

평가 시 반드시 아래를 같이 본다.

- `majority baseline`
- `conditional majority baseline`
- model `Top-1`
- model `Top-3`
- improvement over baseline

현재 프로젝트에서는 단순 accuracy만 보면 안 된다.

예:

- multiclass model `26%`
- majority baseline `37%`

이면 이 모델은 실전적으로 나쁜 모델이다.

## 8. Concrete Recommendation For This Project

지금 당장 가장 좋은 실행 순서는 다음과 같다.

1. batter rolling stats 확장
   - `OBP / SLG / OPS / ISO / BB% / K%`
2. first_pitch_tendency table 유지 및 정교화
3. batter weakness prior + live blend 추가
4. `pitch_family`, `two_seam vs non-two_seam`, `zone_9` 모델 먼저 안정화
5. direct pitch_type multiclass는 보조 실험으로 유지
6. 이후 `2구`, `타석 전체`, `이닝 시퀀스`로 확장

## 9. Final Judgment

현재 데이터와 실험 결과를 기준으로 보면, 이 프로젝트의 최적 방향은 아래다.

- `single-step exact pitch type prediction`이 아니라
- `state-aware staged prediction system`

즉,

- 먼저 `무슨 계열인가`
- 어디로 갈 가능성이 높은가
- 그 다음에 세부 구종을 좁히는 구조

가 가장 현실적이고, 현재 데이터 regime에도 잘 맞는다.
