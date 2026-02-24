#!/usr/bin/env node
/**
 * Claude OpenAI-compatible bridge for OpenClaw
 * Exposes Claude Code CLI as an OpenAI /v1/chat/completions endpoint
 * Port: 18792
 */
const http = require('http');
const { spawn } = require('child_process');
const PORT = 18792;

function cleanEnv() {
  const env = { ...process.env };
  for (const k of Object.keys(env)) {
    if (k.startsWith('CLAUDE') && k !== 'CLAUDE_WORKSPACE') delete env[k];
  }
  return env;
}

function callClaude(prompt, model = 'sonnet') {
  return new Promise((resolve, reject) => {
    const args = ['-p', prompt, '--no-session-persistence', '--disable-slash-commands',
      '--dangerously-skip-permissions', '--model', model, '--max-turns', '1'];
    const proc = spawn('claude', args, {
      env: cleanEnv(),
      timeout: 120000,
      shell: true
    });
    let out = '', err = '';
    proc.stdout.on('data', d => out += d);
    proc.stderr.on('data', d => err += d);
    proc.on('close', code => {
      if (code === 0 && out.trim()) resolve(out.trim());
      else reject(new Error(err || `exit ${code}`));
    });
    proc.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/v1/models') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      data: [
        { id: 'claude-sonnet', object: 'model', owned_by: 'anthropic' },
        { id: 'claude-haiku', object: 'model', owned_by: 'anthropic' },
        { id: 'claude-opus', object: 'model', owned_by: 'anthropic' }
      ]
    }));
    return;
  }

  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', service: 'claude-openai-bridge', port: PORT }));
    return;
  }

  if (req.method === 'POST' && req.url === '/v1/chat/completions') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const data = JSON.parse(body);
        const messages = data.messages || [];
        const prompt = messages.map(m => m.content).join('\n');
        const modelId = data.model || 'claude-sonnet';
        const model = modelId.includes('opus') ? 'opus' : modelId.includes('haiku') ? 'haiku' : 'sonnet';

        console.log(`[${new Date().toISOString()}] ${model}: ${prompt.substring(0, 80)}...`);
        const result = await callClaude(prompt, model);

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          id: 'chatcmpl-' + Date.now(),
          object: 'chat.completion',
          model: modelId,
          choices: [{
            index: 0,
            message: { role: 'assistant', content: result },
            finish_reason: 'stop'
          }],
          usage: { prompt_tokens: prompt.length, completion_tokens: result.length, total_tokens: prompt.length + result.length }
        }));
      } catch (e) {
        console.error(`[ERROR] ${e.message}`);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: { message: e.message, type: 'server_error' } }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end('Not Found');
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Claude OpenAI Bridge running on http://127.0.0.1:${PORT}`);
  console.log('Models: claude-sonnet, claude-haiku, claude-opus');
});
