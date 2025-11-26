const { chromium } = require('playwright');
const http = require('http');

const WS_PORT = 3001;
const HTTP_PORT = 3000;

async function startServer() {
  const browserServer = await chromium.launchServer({
    headless: true,
    port: WS_PORT,
    host: '0.0.0.0',
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
      // Return the endpoint - client will need to replace host
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        wsEndpoint,
        wsPath: wsEndpoint.split(':' + WS_PORT)[1], // Just the path part
        wsPort: WS_PORT
      }));
    } else {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end('Playwright Browser Server Running');
    }
  });

  httpServer.listen(HTTP_PORT, '0.0.0.0', () => {
    console.log(`HTTP server on port ${HTTP_PORT}`);
    console.log(`WebSocket server on port ${WS_PORT}`);
  });

  process.on('SIGINT', async () => {
    await browserServer.close();
    httpServer.close();
    process.exit(0);
  });
}

startServer().catch(console.error);
