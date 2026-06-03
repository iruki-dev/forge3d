# WORKFLOW — Claude Code로 이 프로젝트 진행하기

> 공식 베스트 프랙티스(https://code.claude.com/docs/en/best-practices)를 이 프로젝트에 맞춰 정리.
> 기준 문서: 순서는 `docs/ROADMAP.md`, 작업 단위는 `docs/specs/phase-N-*.md`, 상태는 `docs/PROGRESS.md`.

---

## 1. Phase 단위 실행 루프 (탐색 → 계획 → 구현 → 검증 → 리뷰 → 커밋)

각 Phase는 다음 사이클로 진행한다. **한 Phase = 깨끗한 세션 하나**가 이상적이다.

1. **탐색 (plan mode)**
   plan mode로 진입해 코드만 읽고 질문에 답하게 한다(변경 없음). 예: "ROADMAP의 Phase 2 범위에서 dynamics/와 math/가 어떻게 연결되는지 읽고 설명해라." Phase가 크면 인터뷰로 시작:
   > "ROADMAP의 Phase N을 구현하려 한다. AskUserQuestion 도구로 나를 인터뷰해서 docs/specs/phase-N-*.md SPEC을 완성해라. 기술 구현·엣지 케이스·검증 방법·트레이드오프를 깊게 물어라."

2. **스펙 확정**
   결과를 `docs/specs/SPEC.template.md` 형식으로 저장. 자기완결적으로(관련 파일·인터페이스 명시, 범위 밖 적시, 종단 검증으로 종료). `Ctrl+G`로 계획을 에디터에서 직접 수정 가능.

3. **새 세션에서 구현**
   `/clear` 또는 새 세션으로 컨텍스트를 비우고, SPEC을 기준으로 task를 **하나씩** 구현한다. 깨끗한 컨텍스트가 구현에만 집중된다.

4. **task마다 검증 (게이트)**
   `pytest → ruff → mypy`를 실제로 실행하고 출력을 보인다. 물리 코드면 ROADMAP §13의 정확성 게이트(보존법칙/해석해/기준엔진/백엔드 일치)도 통과시킨다. **Phase 검증 기준을 통과하기 전에는 다음 Phase로 넘어가지 않는다.**

5. **독립 리뷰**
   서브에이전트로 diff를 SPEC과 대조 검토:
   > "이 diff를 docs/specs/phase-N-*.md와 대조해라. 모든 요구사항 구현·명시된 엣지 케이스 테스트·범위 밖 변경 여부를 확인하고, 정확성/요구사항에 영향 주는 누락만 보고해라."
   번들 `/code-review` 스킬로 일반 버그 검토도 가능.

6. **커밋 + 상태 갱신**
   서술형 메시지로 커밋하고 PR 생성. SPEC 체크박스와 `docs/PROGRESS.md`를 갱신한다.

## 2. 일회성 환경 설정 (한 번 해두면 계속 이득)

- **`/init`**로 CLAUDE.md 초안 생성 → 루트 `CLAUDE.md`의 얇은 형식으로 정리.
- **검증을 hook으로 강제**: hook은 조언이 아니라 결정적이다. "파일 편집 후 ruff를 돌리는 hook을 작성해줘", "src/forge3d/에서 pybullet·mujoco import를 차단하는 hook을 작성해줘", **"물리 코어 패키지(math/dynamics/collision/contact/model/sim)에서 forge3d.render import를 차단하는 hook을 작성해줘"**처럼 Claude에게 직접 짜게 한다(`.claude/settings.json`, `/hooks`로 확인). Stop hook으로 pytest 통과 전 턴 종료를 막을 수도 있다 — 무인 실행에 특히 유용.
- **권한 허용 목록**: `/permissions`로 `pytest`, `ruff`, `git commit` 같은 안전한 명령을 allowlist에 넣어 승인 클릭을 줄인다. 신뢰하는 흐름은 auto mode.
- **CLI 도구**: GitHub을 쓰면 `gh` 설치(이슈·PR·코멘트가 토큰 효율적). `docker` CLI도 마찬가지.
- **스킬로 도메인 지식 분리**: 가끔만 필요한 규칙(예: "RNEA 손유도 검증 절차", "기준엔진 대조 작성법")은 CLAUDE.md 대신 `.claude/skills/<name>/SKILL.md`로 두면 필요할 때만 로딩되어 컨텍스트를 아낀다.
- **검증 서브에이전트**: `.claude/agents/`에 물리 검증·코드 리뷰 전용 에이전트를 정의해, 메인 대화를 더럽히지 않고 격리 검토.

## 3. 컨텍스트 위생 (CPU·장기 프로젝트에서 특히 중요)

- 컨텍스트가 차면 성능이 떨어진다. **관련 없는 작업 사이에는 `/clear`**로 초기화한다.
- 같은 문제로 **두 번 넘게 교정**했다면 컨텍스트가 실패 시도로 오염된 것 → `/clear` 후 배운 점을 반영한 더 구체적인 프롬프트로 새로 시작.
- 코드베이스 조사처럼 **파일을 많이 읽는 작업은 서브에이전트에 위임**(별도 컨텍스트에서 돌고 요약만 보고). 무절제한 "investigate"로 메인 컨텍스트를 채우지 않는다.
- 긴 작업은 `/compact <지시>`로 핵심만 남기고, 작업이 여러 날 걸치면 `claude --resume`과 `/rename`으로 Phase별 세션을 분리 관리.

## 4. 흔한 실패와 처방

- **검증 없는 완료 주장**(이 프로젝트 1순위 위험): 테스트·기준엔진 대조 없이 "동작함"이라 말하지 않는다. 검증 못 하면 배포하지 않는다.
- **무절제 탐색**: 조사는 범위를 좁히거나 서브에이전트로.
- **CLAUDE.md 비대화**: 규칙이 묻혀 무시되면 가차없이 잘라낸다. 매번 필요한 강제 규칙은 hook으로 옮긴다.
- **kitchen-sink 세션**: 무관한 일을 한 세션에 섞지 말고 `/clear`.

## 5. 이 프로젝트 특화 주의

- **외부 물리엔진을 코어에 끌어들이지 않도록 hook + CLAUDE.md로 이중 차단**한다(가장 어기기 쉬운 가드레일).
- **물리↔렌더 분리 강제**: 물리 코어는 `forge3d.render`를 import하지 않는다. 연결은 `SceneSnapshot`뿐. hook + 리뷰로 확인.
- **라이브러리/응용 분리 강제**: `apps/robot_rl/`은 `src/forge3d/`를 외부인처럼 import만 한다. 응용을 짜려고 라이브러리를 고쳐야 하면 추상화 실패 신호 — 멈추고 보고. `examples/`가 내부 접근 없이 15줄 내로 도는지로 검증.
- **렌더러 먼저(P3~4) → 이후 전부 "보면서" 개발**: 접촉·RL 단계의 물리 버그는 숫자가 아니라 화면으로 잡는 게 훨씬 빠르다. 새 물리 거동을 구현하면 실시간 뷰어로 눈 확인을 디버깅 루프에 포함한다.
- 엔진 코드는 **np/jnp 양쪽에서 테스트**한다: `ENGINE_BACKEND=numpy pytest` 와 `ENGINE_BACKEND=jax pytest` 둘 다.
- 성능화(P11) 전까지는 **NumPy 경로로 정확성**을 먼저 닫는다(디버깅이 쉽다). 정확성 확인 뒤 JAX로 JIT/vmap 최적화.
- **헤드리스 렌더 가용성**을 가정하지 않는다: OpenGL 오프스크린(EGL/Xvfb)이 컨테이너에서 되는지 P3 착수 시 먼저 확인하고, 안 되면 소프트 래스터라이저 경로를 SPEC에 명시.
