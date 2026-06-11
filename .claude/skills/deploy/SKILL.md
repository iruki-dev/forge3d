# Skill: deploy

문서 사이트를 GitHub Pages에 배포한다.

## 반드시 지켜야 할 순서

```
1. git add <변경된 파일들>
2. git commit
3. git push origin main          ← 소스가 main에 먼저 들어가야 한다
4. mkdocs gh-deploy --force      ← 렌더링 결과를 gh-pages에 올린다
```

**`mkdocs gh-deploy`만 실행하면 소스(`docs_src/`)는 main에 기록되지 않는다.**
렌더링된 HTML만 `gh-pages` 브랜치에 올라가고, 소스는 사라진다.

## 배포 전 체크리스트

- [ ] `mkdocs build` 오류 없이 성공하는가?
- [ ] `site/` 안에 새 페이지가 생성됐는가?
- [ ] 변경된 `docs_src/` 파일이 staging에 포함됐는가?
- [ ] `git status`에 누락된 파일이 없는가?

## 전체 예시

```bash
# 1. 변경 파일 스테이징
git add docs_src/ mkdocs.yml README.md CHANGELOG.md

# 2. 커밋
git commit -m "docs: update ECS API examples and add editor page"

# 3. main에 push
git push origin main

# 4. 문서 사이트 배포
mkdocs gh-deploy --force
```

## 배포 URL

- GitHub Pages: https://iruki-dev.github.io/forge3d/
- 브랜치: `gh-pages` (자동 관리, 직접 수정 금지)
- 소스: `docs_src/` (docs_dir in mkdocs.yml)
