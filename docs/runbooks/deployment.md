# Deployment Runbook

Guide for deploying WondersTracker to production and staging environments.

## Environments

| Environment | Branch | URL | Purpose |
|-------------|--------|-----|---------|
| Production | `main` | wonderstracker.com | Live users |
| Staging | `staging` | staging.wonderstracker.com | Pre-release testing |
| Preview | `preview` | preview.wonderstracker.com | Feature previews |

## Deployment Flow

```
feature-branch → PR → staging → PR → main → Production
                      ↓              ↓
                   Staging        Production
                   Auto-deploy    Auto-deploy
```

## Railway (Backend)

### Automatic Deployments

Railway auto-deploys on push to configured branches:
- `main` → Production service
- `staging` → Staging service

### Manual Deployment

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Deploy to production
railway up --service wonder-scraper
```

### Environment Variables

Set in Railway Dashboard → Service → Variables:

Required:
- `DATABASE_URL` - Neon PostgreSQL connection string
- `SECRET_KEY` - JWT signing key

Optional:
- `DISCORD_UPDATES_WEBHOOK_URL`
- `OPENROUTER_API_KEY`
- `POLAR_ACCESS_TOKEN`

### Rollback

```bash
# View recent deployments
railway deployments

# Rollback to previous deployment
railway rollback
```

## Vercel (Frontend)

### Automatic Deployments

Vercel auto-deploys on push:
- `main` → Production
- Other branches → Preview deployments

### Manual Deployment

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy to production
cd frontend
vercel --prod

# Deploy preview
vercel
```

### Environment Variables

Set in Vercel Dashboard → Project → Settings → Environment Variables:

- `VITE_API_URL` - Backend API URL

## Database Migrations

### Before Deploying Schema Changes

1. Test migration locally:
   ```bash
   poetry run alembic upgrade head
   ```

2. Test rollback:
   ```bash
   poetry run alembic downgrade -1
   poetry run alembic upgrade head
   ```

3. For staging, deploy and verify before production

### Running Migrations in Production

Migrations run automatically on deployment via the start command.

For manual execution:
```bash
# Connect to Railway shell
railway run poetry run alembic upgrade head
```

## Health Checks

### Backend
- **Endpoint**: `GET /health`
- **Expected**: `{"status": "healthy"}`

### Monitoring

```bash
# Check Railway logs
railway logs

# Check specific deployment
railway logs --deployment <id>
```

## Incident Response

### Backend Down

1. Check Railway dashboard for deployment status
2. Check logs: `railway logs`
3. If recent deploy, rollback: `railway rollback`
4. Check Neon database status

### Database Issues

1. Check Neon dashboard for connection issues
2. Verify connection pooling isn't exhausted
3. Check for long-running queries
4. Contact Neon support if needed

### High Error Rate

1. Check error logs in Railway
2. Identify failing endpoints
3. Check external service status (eBay, Discord)
4. Deploy hotfix or rollback

## Pre-Deployment Checklist

- [ ] Tests pass locally (`poetry run pytest`)
- [ ] Frontend builds (`cd frontend && npm run build`)
- [ ] No secrets in code
- [ ] Migration tested locally
- [ ] PR reviewed and approved
- [ ] Staging tested (if applicable)

## Post-Deployment Checklist

- [ ] Health check passes
- [ ] Key features work (login, card search, pricing)
- [ ] No errors in logs
- [ ] Monitor for 15 minutes
- [ ] Update status page (if applicable)
