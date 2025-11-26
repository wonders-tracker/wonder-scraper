const { chromium } = require('playwright');
const http = require('http');

async function startServer() {
  const browserServer = await chromium.launchServer({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  });

  const wsEndpoint = browserServer.wsEndpoint();
  console.log(`Browser WebSocket endpoint: ${wsEndpoint}`);

  // HTTP server to expose the WebSocket endpoint
  const httpServer = http.createServer((req, res) => {
    if (req.url === '/ws-endpoint') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ wsEndpoint }));
    } else {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end('Playwright Browser Server Running');
    }
  });

  httpServer.listen(3000, '0.0.0.0', () => {
    console.log('HTTP server listening on port 3000');
    console.log('Get WebSocket endpoint at: http://0.0.0.0:3000/ws-endpoint');
  });

  process.on('SIGINT', async () => {
    await browserServer.close();
    httpServer.close();
    process.exit(0);
  });
}

startServer().catch(console.error);
