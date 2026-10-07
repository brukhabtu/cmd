---
id: TASK-1.44
title: Publish the documentation site
status: In Progress
assignee: []
created_date: '2026-10-07 12:14'
updated_date: '2026-10-07 13:03'
labels:
  - size-1
milestone: m-3
dependencies: []
parent_task_id: TASK-1
ordinal: 43000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Deploy the site TASK-1.42 builds, for example to GitHub Pages from the default branch, once the owner decides where it lives.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each release, and no push, rebuilds the site from the release's tag and serves it at a stable URL; a pre-release does not publish it
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
The owner chose GitHub Pages, and that only releases publish (2026-10-07).
1. .github/workflows/pages.yml on release (type released, so pre-releases do not publish): a build job (contents: read) checks out the tag, runs scripts/docs.sh (the strict build check.sh runs, with folder URLs) and uploads site/ with actions/upload-pages-artifact@v5; a deploy job (pages: write, id-token: write, the github-pages environment) runs actions/deploy-pages@v5.
2. mkdocs.yml: site_url https://brukhabtu.github.io/cmd/, which the 404 page needs for its links under /cmd/, and the sitemap and canonical links use.
3. README, CLAUDE.md and the workflow's header say where the site lives and what publishes it.
4. Only the owner can change the two settings: Pages on with GitHub Actions as the source, and the github-pages environment allowing tags (a release runs on its tag; GitHub lets only the default branch deploy by default).
Proof: actionlint and check.sh clean; after the settings, a release's run deploys and the URL serves the site.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07: pages.yml, site_url and the docs are in. actionlint passes all three workflows; scripts/docs.sh builds strict with folder URLs; the 404 page links /cmd/assets/..., and the sitemap and canonical links use the Pages address. Waiting on the owner: the two settings in the plan, then a release. The task closes on a release's deploy serving https://brukhabtu.github.io/cmd/.
<!-- SECTION:NOTES:END -->
