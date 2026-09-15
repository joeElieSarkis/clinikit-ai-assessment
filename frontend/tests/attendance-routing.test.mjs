import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { createServer } from 'vite';

test('development navigation serves the report instead of the reception fallback', async () => {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const server = await createServer({
    root,
    configFile: fileURLToPath(new URL('../vite.config.ts', import.meta.url)),
    server: { host: '127.0.0.1', port: 0, open: false },
    logLevel: 'error',
  });
  try {
    await server.listen();
    const address = server.httpServer.address();
    assert.ok(address && typeof address !== 'string');
    const origin = `http://127.0.0.1:${address.port}`;
    for (const path of [
      '/attendance',
      '/attendance/',
      '/attendance/?review=1',
      '/attendance/index.html',
    ]) {
      const response = await fetch(origin + path, { headers: { Accept: 'text/html' } });
      assert.equal(response.status, 200, path);
      const html = await response.text();
      assert.match(html, /id="results-data"/, path);
      assert.match(html, /Understanding/, path);
      assert.doesNotMatch(html, /src="\/src\/main\.tsx"/, path);
    }
    const reception = await fetch(origin + '/');
    assert.equal(reception.status, 200);
    assert.match(await reception.text(), /src="\/src\/main\.tsx"/);
  } finally {
    await server.close();
  }
});
