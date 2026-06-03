# SPECs — 인덱스

각 Phase의 실행 기준 문서. **순서·전체 맥락은 `../ROADMAP.md`**, 작업 규칙은 `../../CLAUDE.md`, 절차는 `../WORKFLOW.md`.

## 정책 — 적시(just-in-time) 작성
공식 권장에 따라, **상세 SPEC은 해당 Phase에 착수하기 직전에 작성**한다(세부는 앞 Phase를 끝내며 분명해진다). 아래 P0~P2는 즉시 실행 가능한 완성본이고, P3 이후는 ROADMAP에 고수준이 정의되어 있으며 착수 시 `SPEC.template.md`로 구체화한다.

## 목록

| Phase | SPEC | 상태 |
|-------|------|------|
| 0 | [phase-0-bootstrap.md](phase-0-bootstrap.md) | 작성 완료 |
| 1 | [phase-1-math-and-2dof.md](phase-1-math-and-2dof.md) | 작성 완료 |
| 2 | [phase-2-ndof-dynamics.md](phase-2-ndof-dynamics.md) | 작성 완료 |
| 3 ★ | [phase-3-snapshot-realtime.md](phase-3-snapshot-realtime.md) | 작성 완료 |
| 4 ★ | [phase-4-facade-api.md](phase-4-facade-api.md) | 작성 완료 |
| 5 | 충돌(프리미티브) + 연성 접촉(Phase A) | 착수 시 작성 |
| 6 ★ | 고품질 레이트레이서 + Recorder | 착수 시 작성 |
| 7 | 로봇 모델 + 그리퍼 + 인터랙티브 조작 UI | 착수 시 작성 |
| 8 | Gymnasium 환경(reaching) + render_mode 3종 | 착수 시 작성 |
| 9 | Reaching RL 완주 + 대시보드 | 착수 시 작성 |
| 10 | 파지 weld 추상화 + pick-and-place | 착수 시 작성 |
| 11 | all-JAX 성능화 + SHAC | 착수 시 작성 |
| 12 (선택) | 실접촉 마찰 파지·GJK/EPA·도메인 랜덤화 | 착수 시 작성 |

## 새 SPEC 만들기
`SPEC.template.md`를 복사하거나, plan mode에서 "AskUserQuestion으로 나를 인터뷰해서 phase-N SPEC을 완성해라"로 생성한다.
