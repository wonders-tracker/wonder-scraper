import { createFileRoute, Link } from '@tanstack/react-router'
import { Key, Lock, Shield, AlertTriangle, Clock } from 'lucide-react'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/authentication')({
  component: DocsAuthentication,
})

const curlExample = `curl -H "X-API-Key: wt_your_api_key_here" \\
     https://api.wonderstrader.com/api/v1/cards`

const headersExample = `X-RateLimit-Limit: 60
X-RateLimit-Remaining: 58
X-RateLimit-Reset: 1702156800
Retry-After: 30  # (only on 429 responses)`

const pythonExample = `import os
import requests

API_KEY = os.environ.get("WONDERS_API_KEY")
headers = {"X-API-Key": API_KEY}

response = requests.get(
    "https://api.wonderstrader.com/api/v1/cards",
    headers=headers
)`

const jsExample = `const API_KEY = process.env.WONDERS_API_KEY;

const response = await fetch(
  "https://api.wonderstrader.com/api/v1/cards",
  { headers: { "X-API-Key": API_KEY } }
);`

function DocsAuthentication() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Authentication</h1>
        <p className="text-lg text-muted-foreground">
          API keys and rate limits for accessing the WondersTracker API.
        </p>
      </div>

      {/* API Key Authentication */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Key className="w-5 h-5 text-amber-500" />
          API Key Authentication
        </h2>
        <p className="text-muted-foreground mb-4">
          All API requests require authentication via an API key. Include your key in the{' '}
          <code className="bg-muted px-1.5 py-0.5 rounded">X-API-Key</code> header.
        </p>
        <CodeBlock code={curlExample} language="bash" />
        <p className="text-sm text-muted-foreground mt-4">
          <Link to="/api" className="text-primary hover:underline">
            Get your API key
          </Link>{' '}
          from the API Access page.
        </p>
      </section>

      {/* API Key Format */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="text-lg font-bold mb-4">API Key Format</h2>
        <p className="text-muted-foreground mb-4">
          Keys are prefixed with <code className="bg-muted px-1.5 py-0.5 rounded">wt_</code> for identification:
        </p>
        <div className="bg-zinc-900 rounded-lg p-4 font-mono text-sm">
          <code className="text-zinc-400">wt_1a2b3c4d5e6f7g8h9i0j...</code>
        </div>
        <p className="text-sm text-muted-foreground mt-4">
          Only the prefix is stored in our database - the full key is hashed for security.
        </p>
      </section>

      {/* Rate Limits */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-red-500" />
          Rate Limits
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="border rounded-lg p-4 bg-muted/20">
            <div className="text-2xl font-bold text-primary">60</div>
            <div className="text-xs uppercase text-muted-foreground">Requests / Minute</div>
          </div>
          <div className="border rounded-lg p-4 bg-muted/20">
            <div className="text-2xl font-bold text-primary">10,000</div>
            <div className="text-xs uppercase text-muted-foreground">Requests / Day</div>
          </div>
          <div className="border rounded-lg p-4 bg-muted/20">
            <div className="text-2xl font-bold text-primary">10</div>
            <div className="text-xs uppercase text-muted-foreground">Burst / 5 sec</div>
          </div>
        </div>

        <div className="space-y-3 text-sm">
          <div className="flex items-start gap-3">
            <Clock className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
            <div>
              <strong className="text-foreground">Daily Reset:</strong>{' '}
              <span className="text-muted-foreground">Limits reset at midnight UTC.</span>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
            <div>
              <strong className="text-foreground">Rate Exceeded:</strong>{' '}
              <span className="text-muted-foreground">
                Returns HTTP 429 with <code className="bg-muted px-1 rounded">Retry-After</code> header.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Response Headers */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="text-lg font-bold mb-4">Rate Limit Headers</h2>
        <p className="text-muted-foreground mb-4">
          Each response includes headers showing your current rate limit status:
        </p>
        <CodeBlock code={headersExample} language="bash" />
      </section>

      {/* Security */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Lock className="w-5 h-5 text-green-500" />
          Security Best Practices
        </h2>
        <ul className="space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-brand-300 font-bold">1.</span>
            <span><strong className="text-foreground">Never share your API key</strong> - Treat it like a password</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300 font-bold">2.</span>
            <span><strong className="text-foreground">Use environment variables</strong> - Don't hardcode keys in code</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300 font-bold">3.</span>
            <span><strong className="text-foreground">Rotate compromised keys</strong> - Delete and regenerate if exposed</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300 font-bold">4.</span>
            <span><strong className="text-foreground">Use HTTPS only</strong> - All API requests must use HTTPS</span>
          </li>
        </ul>
      </section>

      {/* Example Code */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="text-lg font-bold mb-4">Example: Secure Key Storage</h2>

        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-bold uppercase text-muted-foreground mb-2">Python</h3>
            <CodeBlock code={pythonExample} language="typescript" />
          </div>

          <div>
            <h3 className="text-sm font-bold uppercase text-muted-foreground mb-2">JavaScript</h3>
            <CodeBlock code={jsExample} language="javascript" />
          </div>
        </div>
      </section>
    </div>
  )
}
