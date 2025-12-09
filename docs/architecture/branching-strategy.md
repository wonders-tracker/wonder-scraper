# Branching Strategy & Protection Rules

Guide for repository branching strategy and GitHub branch protection configuration.

## Branch Overview

```
main (production)
  ↑ PR required
staging (pre-release)
  ↑ PR required
preview (feature preview)
  ↑ Direct push allowed
feature/* (development)
```

## Branch Purposes

### `main` (Production)
- **Deploys to**: Production environment
- **Protection**: Strictest - requires PR, reviews, CI pass
- **Who merges**: Maintainers only
- **Source**: PRs from `staging` only

### `staging` (Pre-Release)
- **Deploys to**: Staging environment
- **Protection**: Requires PR and CI pass
- **Who merges**: Contributors with approval
- **Source**: PRs from feature branches

### `preview` (Feature Preview)
- **Deploys to**: Preview environment
- **Protection**: Minimal - direct push allowed
- **Who merges**: Anyone with write access
- **Purpose**: Quick previews and demos

### Feature Branches
- **Naming**: `feature/description`, `fix/description`, `docs/description`
- **Protection**: None
- **Lifecycle**: Create → Work → PR to staging → Delete after merge

## GitHub Branch Protection Setup

### For `main` branch

Go to **Settings → Branches → Add rule** for `main`:

```
✅ Require a pull request before merging
   ✅ Require approvals: 1
   ✅ Dismiss stale pull request approvals when new commits are pushed
   ✅ Require review from Code Owners (if CODEOWNERS file exists)

✅ Require status checks to pass before merging
   ✅ Require branches to be up to date before merging
   Status checks required:
   - Backend Tests
   - Frontend Tests
   - Backend Lint

✅ Require conversation resolution before merging

✅ Require linear history

❌ Allow force pushes (DISABLED)

❌ Allow deletions (DISABLED)
```

### For `staging` branch

```
✅ Require a pull request before merging
   ✅ Require approvals: 1

✅ Require status checks to pass before merging
   Status checks required:
   - Backend Tests
   - Frontend Tests

❌ Allow force pushes (DISABLED)
```

### For `preview` branch

```
❌ No protection rules (allow direct push for quick previews)
```

## Workflow Examples

### Adding a New Feature

```bash
# 1. Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/portfolio-export

# 2. Make changes, commit regularly
git add .
git commit -m "feat(portfolio): add CSV export"

# 3. Push and create PR to staging
git push -u origin feature/portfolio-export
# Open PR: feature/portfolio-export → staging

# 4. After staging merge and testing, PR to main
# Open PR: staging → main

# 5. Clean up
git checkout main
git pull
git branch -d feature/portfolio-export
```

### Hotfix Process

```bash
# 1. Create hotfix branch from main
git checkout main
git pull
git checkout -b fix/critical-bug

# 2. Fix and commit
git commit -m "fix: resolve critical pricing bug"

# 3. PR directly to main (skip staging for critical fixes)
git push -u origin fix/critical-bug
# Open PR: fix/critical-bug → main (mark as hotfix)

# 4. After merge, backport to staging
git checkout staging
git pull origin main
git push
```

## CODEOWNERS (Optional)

Create `.github/CODEOWNERS` to require specific reviewers:

```
# Default owners
* @codyrobertson

# Frontend changes need frontend review
/frontend/ @codyrobertson

# Backend changes need backend review
/app/ @codyrobertson

# Infrastructure changes
/.github/ @codyrobertson
/docker-compose.yml @codyrobertson
```

## Release Process

### Semantic Versioning

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes

### Creating a Release

1. Ensure `main` is stable
2. Create release on GitHub:
   - Go to **Releases → Draft new release**
   - Tag: `v1.2.3`
   - Target: `main`
   - Generate release notes
3. Railway auto-deploys tagged releases

## CI/CD Integration

### Status Checks

The following checks must pass before merging to protected branches:

| Check | Description | Blocking |
|-------|-------------|----------|
| `Backend Tests` | pytest suite | Yes |
| `Backend Lint` | ruff linting | No (warning) |
| `Frontend Tests` | typecheck + build | Yes |
| `Security Scan` | Trivy vulnerability scan | No (warning) |

### Auto-Deployment

| Branch | Trigger | Target |
|--------|---------|--------|
| `main` | Push/Merge | Production (Railway) |
| `staging` | Push/Merge | Staging (Railway) |
| `preview` | Push | Preview (Railway) |

## Troubleshooting

### "Required status check is expected"
- CI workflow hasn't run yet
- Push a commit or re-run the workflow

### "Branch is out of date"
- Click "Update branch" in PR
- Or locally: `git checkout feature && git merge main`

### "Merge blocked by branch protection"
- Ensure all required checks pass
- Get required approvals
- Resolve all conversations
