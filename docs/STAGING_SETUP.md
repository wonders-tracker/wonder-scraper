# Staging Environment Setup Guide

This guide walks through setting up the complete staging environment.

## Current Staging Environment

| Component | URL/Value |
|-----------|-----------|
| **Backend** | https://wonder-scraper-staging-staging.up.railway.app |
| **Health Check** | https://wonder-scraper-staging-staging.up.railway.app/health |
| **Detailed Health** | https://wonder-scraper-staging-staging.up.railway.app/health/detailed |
| **Circuit Breakers** | https://wonder-scraper-staging-staging.up.railway.app/health/circuits |
| **Database** | Neon `staging` branch |
| **Railway Service** | `wonder-scraper-staging` in `staging` environment |
| **Railway Project** | `dynamic-prosperity` |

## Current Production Environment

| Component | URL/Value |
|-----------|-----------|
| **Backend** | https://wonder-scraper-production.up.railway.app |
| **Frontend** | https://wonderstracker.com |
| **API (via proxy)** | https://wonderstracker.com/api/v1 |
| **Database** | Neon `main` branch |
| **Railway Service** | `wonder-scraper` in `production` environment |

## Prerequisites

- Railway account with existing production service
- Neon account with existing production database
- GitHub repo admin access (for branch protection)
- Vercel account (already configured)

## Step 1: Neon Database Staging Branch

Neon's branching creates an instant copy-on-write clone of your production database.

### Create Staging Branch

1. Go to [Neon Console](https://console.neon.tech)
2. Select your project
3. Click **Branches** in the sidebar
4. Click **Create Branch**
5. Configure:
   - **Name:** `staging`
   - **Parent branch:** `main` (your production branch)
   - **Include data:** Yes (copies current prod data)
6. Click **Create Branch**

### Get Staging Connection String

1. Select the new `staging` branch
2. Click **Connection Details**
3. Copy the **Pooled connection string** (ends with `-pooler`)
4. Save this for Railway configuration

**Example:**
```
postgresql://user:pass@ep-xxx-staging-pooler.region.aws.neon.tech/neondb?sslmode=require
```

### Reset Staging to Production (When Needed)

To refresh staging with latest production data:
1. Delete the staging branch
2. Recreate it from main (same steps as above)

Or use Neon CLI:
```bash
neonctl branches delete staging --project-id <your-project-id>
neonctl branches create --name staging --parent main --project-id <your-project-id>
```

## Step 2: Railway Staging Service

### Create New Service

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Open your project
3. Click **New Service** → **GitHub Repo**
4. Select `wonder-scraper` repository
5. Configure deployment:
   - **Branch:** `staging`
   - **Config Path:** `railway-staging.toml`

### Configure Environment Variables

Add these variables (copy from production, modify as needed):

```bash
# Database - USE STAGING BRANCH URL
DATABASE_URL=postgresql://...staging-pooler.../neondb?sslmode=require

# Security (generate new for isolation)
SECRET_KEY=<generate-new-secret>

# Frontend URL
FRONTEND_URL=https://staging.wonderstracker.com

# Discord (optional - use separate staging webhooks or disable)
DISCORD_LOGS_WEBHOOK_URL=<staging-webhook-or-empty>
DISCORD_UPDATES_WEBHOOK_URL=<staging-webhook-or-empty>

# Scheduler
RUN_SCHEDULER=true

# Other settings (copy from prod)
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=https://staging.wonderstracker.com/api/v1/auth/discord/callback
```

### Generate New SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Verify Deployment

After first deploy:
```bash
curl https://wonder-scraper-staging.up.railway.app/health
curl https://wonder-scraper-staging.up.railway.app/health/detailed
```

## Step 3: Vercel Staging Configuration

Vercel already supports preview deployments. For dedicated staging:

### Option A: Automatic Staging Previews (Recommended)

Vercel automatically creates preview deployments for non-production branches.
The `staging` branch will get a preview URL automatically.

### Option B: Custom Staging Domain

1. Go to Vercel project settings
2. Click **Domains**
3. Add `staging.wonderstracker.com`
4. Configure DNS with your registrar
5. In **Git** settings, set staging branch to deploy to this domain

## Step 4: GitHub Branch Protection

### Protect Main Branch

1. Go to GitHub repo → **Settings** → **Branches**
2. Click **Add branch protection rule**
3. Branch name pattern: `main`
4. Enable:
   - ☑️ Require a pull request before merging
   - ☑️ Require status checks to pass before merging
     - Select: `backend-test`, `backend-lint`, `frontend-test`, `frontend-bundle-integrity`
   - ☑️ Require branches to be up to date before merging
5. Click **Create**

### Protect Staging Branch (Optional)

Same as above but for `staging` branch - less strict if you want faster iteration.

## Step 5: Test the Pipeline

### Create Test Feature

```bash
# Create feature branch
git checkout -b feature/test-staging-pipeline main

# Make a small change (e.g., add comment)
echo "# Test comment" >> README.md

# Push and create PR
git add README.md
git commit -m "test: verify staging pipeline"
git push -u origin feature/test-staging-pipeline

# Create PR to staging
gh pr create --base staging --title "Test staging pipeline"
```

### Verify CI Runs

1. Check GitHub Actions - all checks should run
2. Merge PR to staging
3. Watch Railway deploy staging service
4. Check staging smoke tests pass
5. Verify app works at staging URL

### Promote to Production

```bash
# Create PR from staging to main
gh pr create --base main --head staging --title "Release: test staging pipeline"

# After review, merge to main
# Production auto-deploys
```

## Rollback Procedures

### Code Rollback

Railway has one-click rollback:
1. Go to Railway service
2. Click **Deployments**
3. Find previous working deployment
4. Click **Rollback**

### Database Rollback

Neon has point-in-time recovery:
1. Go to Neon Console → Branches
2. Click **Restore**
3. Select point in time before the issue
4. Creates new branch from that point

Or restore staging from production:
```bash
neonctl branches delete staging
neonctl branches create --name staging --parent main
```

## Monitoring

### Health Checks

```bash
# Staging
curl https://wonder-scraper-staging.up.railway.app/health/detailed
curl https://wonder-scraper-staging.up.railway.app/health/circuits

# Production
curl https://wonderstracker.com/api/v1/health/detailed
```

### Logs

- **Railway:** Dashboard → Service → Logs
- **Vercel:** Dashboard → Project → Functions tab
- **Neon:** Console → Monitoring

## Cost Estimate

| Service | Staging Cost |
|---------|--------------|
| Railway Starter | ~$5/month (included in plan) |
| Neon Free Tier | $0 (10 branches included) |
| Vercel Free Tier | $0 (preview deployments included) |
| **Total** | **~$5/month** |

## Troubleshooting

### Staging deploy fails

1. Check Railway logs for error
2. Verify DATABASE_URL points to staging branch
3. Ensure migrations ran successfully

### CI smoke tests fail

1. Check if Railway deployment finished
2. Verify staging service is running
3. Check health endpoint manually

### Database connection issues

1. Verify Neon staging branch exists
2. Check connection string has `-pooler` suffix
3. Verify IP allowlist (if using Neon's IP restrictions)

## CI/CD Pipeline

### Automated Checks

Every push triggers these CI jobs:

| Job | Duration | Purpose |
|-----|----------|---------|
| backend-test | ~3m | Pytest with PostgreSQL |
| backend-lint | ~30s | Ruff + ty type checker |
| frontend-test | ~45s | TypeScript + ESLint + Build |
| frontend-bundle-integrity | ~8s | Validates production bundle |
| security-scan | ~15s | Trivy vulnerability scan |
| migration-check | ~5s | Detects dangerous migrations (PRs only) |

### Staging-Specific Checks

On push to `staging` branch:

| Job | Duration | Purpose |
|-----|----------|---------|
| staging-smoke-test | ~10s | Health checks + auth validation |

### Production-Specific Checks

On PRs to `main` branch:

| Job | Duration | Purpose |
|-----|----------|---------|
| production-auth-check | ~5s | Validates production OAuth config |

### Auth Configuration Validation

CI automatically validates:
- Discord redirect URI matches expected domain
- HTTPS is used
- Callback path is correct (`/api/v1/auth/discord/callback`)

**Staging:** Redirect URI must match staging Railway URL
**Production:** Redirect URI must NOT point to Railway (must use frontend domain)

## OAuth Configuration

### Discord Redirect URIs

**CRITICAL:** Always update Discord Developer Portal BEFORE changing Railway env vars.

| Environment | Redirect URI |
|-------------|-------------|
| Production | `https://wonderstracker.com/api/v1/auth/discord/callback` |
| Staging | `https://wonder-scraper-staging-staging.up.railway.app/api/v1/auth/discord/callback` |
| Local | `http://localhost:8000/api/v1/auth/discord/callback` |

### Updating Redirect URI

1. Go to https://discord.com/developers/applications
2. Select your app (Client ID: `1441887300081680545`)
3. Go to **OAuth2** → **Redirects**
4. Add the new redirect URI
5. Save changes
6. **THEN** update Railway environment variable:
   ```bash
   railway environment production
   railway variables --set "DISCORD_REDIRECT_URI=https://wonderstracker.com/api/v1/auth/discord/callback"
   railway redeploy -y
   ```

### Why This Matters

Discord OAuth flow:
```
User → Discord Login → Discord Callback → Backend Sets Cookies → Frontend
```

If redirect URI domain ≠ frontend domain, cookies won't be sent to frontend = broken auth.

## Quick Reference

### Deploy to Staging
```bash
# From feature branch
gh pr create --base staging
gh pr merge <PR_NUMBER> --merge
curl https://wonder-scraper-staging-staging.up.railway.app/health
```

### Deploy to Production
```bash
# From staging
gh pr create --base main --head staging --title "Release: description"
gh pr merge <PR_NUMBER> --merge
curl https://wonder-scraper-production.up.railway.app/health
```

### Emergency Rollback
```bash
# Railway rollback
railway environment production
railway rollback

# Or via dashboard: Railway → Deployments → Rollback
```

### Check Logs
```bash
# Staging
railway environment staging
railway logs

# Production
railway environment production
railway logs
```

### Update Environment Variable
```bash
railway environment production  # or staging
railway variables --set "KEY=value"
railway redeploy -y
```
