# White / Catcher Influence Analysis Plan

## 1. Objective

내일 상대를 가정한 사전 판단을 위해 먼저 다음 두 질문을 분리해서 본다.

### 1.1 White 중심 질문

`2025 SSG 화이트의 구종 선택은 상대 타자 특성에 더 반응하는가, 아니면 본인 루틴과 경기 흐름에 더 의해 결정되는가?`

### 1.2 Catcher 중심 질문

`특정 포수의 볼배합 영향은 투수와 무관하게 일관되게 나타나는가?`

이 문서는 화이트 개인 분석과 포수 전체 흐름 분석을 같은 기준 위에서 비교하는 계획서다.

## 2. Available Data Assets

현재 확보된 직접 분석 자산:

- `data/ranges/2025-03-01_2025-10-31/pitches_2025-03-01_2025-10-31.csv`
- `data/matchups/2025_white/pitcher_55855_화이트_SK.csv`
- `data/matchups/2025_white/pitcher_55855_white_context.csv`
- `data/matchups/2025_jo_hyungwoo/catcher_51865_조형우_SK.csv`
- `data/matchups/2025_jo_hyungwoo/catcher_51865_조형우_SK_summary.json`

## 3. Immediate Scope

이번 단계에서는 아래 feature만 우선 사용한다.

- pitcher
- catcher
- batter
- batter stance
- inning / half / outs
- count state
- pitch index in plate appearance
- pitch index in inning
- pitch index in game
- previous pitch types in PA / inning / game
- strike zone 9분할

이번 단계에서 없는 것:

- 주자 상황
- 점수차
- 실시간 leverage

이 항목들은 이후 raw relay를 더 파싱해 확장한다.

## 4. Zone Definition

투구 위치는 좌표 원값 대신 `3 x 3` 존 버킷을 사용한다.

### 4.1 Horizontal bands

- `LEFT`
- `MIDDLE`
- `RIGHT`

기준:

- strike zone width를 3등분

### 4.2 Vertical bands

- `HIGH`
- `MIDDLE`
- `LOW`

기준:

- 각 투구의 `bottom_sz` ~ `top_sz` 구간을 3등분

### 4.3 Final label

- `HIGH_LEFT`
- `HIGH_MIDDLE`
- `HIGH_RIGHT`
- `MIDDLE_LEFT`
- `MIDDLE_MIDDLE`
- `MIDDLE_RIGHT`
- `LOW_LEFT`
- `LOW_MIDDLE`
- `LOW_RIGHT`
- `OUT`

즉 존 내부는 9분할, 존 바깥은 `OUT`으로 따로 둔다.

## 5. White Analysis Design

### 5.1 Basic profile

먼저 화이트의 기본 배합 프로필을 본다.

- 전체 구종 분포
- 타석 첫 구 구종 분포
- 유리 / 불리 카운트별 구종 분포
- 좌타 / 우타 상대 구종 분포
- 포수별 구종 분포
- 존 9분할별 구종 분포

### 5.2 Short sequence questions

- 직전 1구가 무엇이었는가
- 직전 2~3구 조합이 무엇이었는가
- 같은 타석에서 동일 구종 반복 확률은 얼마나 되는가
- 결정구 직전 setup pitch 패턴이 있는가

### 5.3 Mid sequence questions

- 같은 이닝 초반과 후반의 구종 mix가 달라지는가
- 이닝 내 타석 누적에 따라 직구 비율이 변하는가
- 같은 이닝 위기 상황을 대체할 proxy로 outs / count / 연속 타자 흐름이 쓰이는가

### 5.4 Long sequence questions

- 경기 초반 / 중반 / 후반의 구종 mix 변화
- 경기 누적 pitch count에 따라 breaking ball 비중이 증가하는가
- 한 타자를 두 번째, 세 번째 만났을 때 구종 mix가 바뀌는가

## 6. White Influence Test

화이트의 배합이 무엇에 좌우되는지 보기 위해 세 단계 비교를 한다.

### Model A. Routine-only

입력:

- inning / half / outs
- count state
- pitch index in pa / inning / game
- previous pitch types
- zone of previous pitch

의미:

- 화이트가 자기 루틴과 경기 흐름만으로 배합하는지 확인

### Model B. Add batter response

추가 입력:

- batter id
- batter stance
- batter seen count in game

의미:

- 타자 문맥이 들어오면 성능이 얼마나 올라가는지 확인

해석:

- Model B가 크게 좋아지면 타자 반응형 성향이 강함

### Model C. Add catcher context

추가 입력:

- catcher id

의미:

- 같은 화이트라도 포수에 따라 배합이 달라지는지 확인

해석:

- Model C가 의미 있게 좋아지면 포수 영향 또는 배터리 영향이 큼

## 7. Catcher Influence Design

포수 영향은 화이트 데이터만으로 보면 안 된다.

포수는 반드시 `투수 상관없이 그 포수가 받은 전체 투구`로 봐야 한다.

### 7.1 Primary catcher scope

우선 화이트의 주포수였던 `조형우`부터 본다.

필요 시 이후:

- 이지영
- 신범수

까지 확장한다.

### 7.2 Catcher analysis questions

- 조형우가 받는 전체 투구에서 count별 구종 선택 경향이 있는가
- 좌타 / 우타 상대 배합 패턴이 일관적인가
- 존 9분할 목표가 투수와 무관하게 반복되는가
- 직전 구종 이후 다음 구종 전이가 특정 방향으로 기울어지는가

### 7.3 Catcher influence test

조형우 전체 수신 데이터를 기준으로 아래 비교를 한다.

#### Model P. Pitcher-only

- pitcher id
- count
- inning / outs
- previous pitch types

#### Model PC. Pitcher + catcher

- Model P + catcher id

이 비교는 조형우 단독 테이블에서는 불가능하므로, 다음 단계에서는 전체 리그 테이블로 학습해야 한다.

하지만 조형우 전용 분석에서는 아래를 먼저 볼 수 있다.

- pitcher별로 달라도 유지되는 공통 count pattern
- pitcher별로 달라도 유지되는 공통 zone usage
- pitcher별로 달라도 유지되는 transition pattern

즉 학습 전에 descriptive analysis로 포수 시그널이 있는지 확인한다.

## 8. Outputs We Need Next

### 8.1 White report

- overall pitch mix
- count-by-pitch matrix
- stance-by-pitch matrix
- prev_pitch -> next_pitch transition matrix
- zone_9 by pitch type
- catcher split

### 8.2 Catcher report

- catcher overall pitch mix
- pitcher별 mix split
- count-by-pitch matrix
- stance-by-pitch matrix
- prev_pitch -> next_pitch transition matrix
- zone_9 by pitch type

## 9. Recommended Next Execution Order

1. White context table 검증
2. White descriptive report 생성
3. 조형우 descriptive report 생성
4. White routine-only baseline
5. White + batter model
6. White + batter + catcher model
7. 전체 리그 기준 catcher effect model 확장

## 10. Practical Interpretation for Tomorrow

내일 경기 대비용으로는 먼저 아래만 알아도 실전 가치가 크다.

- 화이트의 초구 패턴
- 유리 / 불리 카운트에서의 결정 구종
- 좌타 / 우타 상대 차이
- 조형우와 짝일 때의 구종 변화
- 존 9분할 목표 위치

즉 내일 예측의 1차 버전은:

`화이트 기본 루틴 + 타자 손잡이 + 카운트 + 조형우 조합`

까지 반영한 룰 기반 혹은 baseline 모델로도 충분히 시작할 수 있다.

## 11. Caution On Weakness-Based Claims

타자 약점 정보는 흥미로운 축이지만, 아직 아래 명제는 검증되지 않았다.

- 화이트가 실제로 타자의 약한 방향을 더 자주 공략한다
- 포수가 약점 방향 호출을 일관되게 주도한다

따라서 내일 경기 프리뷰나 README 예측 보드에서는:

- 화이트의 2025 실투구 패턴
- 좌우타 상대 차이
- 카운트 및 직전 구종 흐름
- 포수 조합 경향

까지만 직접 근거로 사용한다.

약점 방향은 별도 검증 리포트가 끝나기 전까지 `보조 가설` 이상으로 쓰지 않는다.
