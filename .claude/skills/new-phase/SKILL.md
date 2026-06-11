# Skill: new-phase

새 Phase를 시작할 때의 전체 절차. CLAUDE.md §1과 docs/WORKFLOW.md의 요약.

## 전제 조건

- **이전 Phase의 검증 기준이 통과됐는가?** → `docs/PROGRESS.md` 확인
- 해당 Phase의 SPEC이 `docs/specs/phase-N-*.md`에 존재하는가?

## 절차

### 1. SPEC 읽기 (plan mode)

```
/plan
"docs/specs/phase-N-*.md 를 읽고,
 범위·파일·완료 조건·검증 게이트를 요약하라.
 현재 코드베이스에서 변경이 필요한 파일 목록을 도출하라."
```

SPEC이 없으면 먼저 인터뷰로 생성:
```
"ROADMAP의 Phase N을 구현하려 한다.
 AskUserQuestion으로 나를 인터뷰해서 SPEC.template.md 형식의 스펙을 완성해라.
 기술 구현·엣지 케이스·검증·트레이드오프를 깊게 물어라."
```

### 2. 구현 (새 세션)

`/clear` 또는 새 세션. SPEC 파일을 컨텍스트 첫 줄에 두고 시작.
task를 **순서대로, 하나씩** 구현한다.

### 3. 검증 (task 완료마다)

```bash
python -m pytest tests/test_pNN_*.py -q --tb=short
ruff check src/ apps/ tests/ demos/
mypy src/
```

물리 코드라면 추가로:
- 에너지·운동량 보존 테스트
- 기준엔진(validation/) 대조
- ENGINE_BACKEND=numpy / =jax 양쪽 테스트

### 4. 커밋

```bash
git add <변경 파일들>
git commit -m "feat(pNN): <Phase 요약>"
git push origin main
```

### 5. PROGRESS.md 갱신

`docs/PROGRESS.md`의 Phase 체크리스트 업데이트:
```
- [x] **PNN** 설명 — 게이트: ... ✅, N tests PASS
```

### 6. 독립 리뷰 (선택)

```
Agent(subagent_type="general-purpose",
  prompt="diff를 docs/specs/phase-N-*.md와 대조해라.
          모든 요구사항 구현·엣지 케이스 테스트·범위 밖 변경을 확인하고
          정확성에 영향 주는 누락만 보고해라.")
```

## 현재 로드맵 상태 (2026-06-11)

- **P0~P35**: 전부 완료 (`docs/PROGRESS.md` 참고)
- **다음**: 새 Phase가 ROADMAP_v2.md에 추가되거나 사용자가 지정

## 핵심 제약 (항상)

- 외부 물리엔진(`pybullet`, `mujoco`) — `src/forge3d/` 안에서 절대 금지
- 렌더러(`forge3d.render`) — 물리 코어(`math/ dynamics/ collision/ contact/ model/ sim/`) 에서 import 금지
- 응용(`apps/`) — 라이브러리를 외부인처럼 import만 한다. 내부를 직접 수정하면 안 된다
