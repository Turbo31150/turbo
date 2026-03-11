#!/usr/bin/env node
/**
 * gemini-openai-proxy.js — Proxy OpenAI-compatible pour Gemini CLI
 *
 * Wrappe le Gemini CLI (authentifié OAuth) en serveur HTTP
 * compatible OpenAI /v1/chat/completions.
 *
 * Port: 18793
 * Usage: node gemini-openai-proxy.js
 * Health: curl http://127.0.0.1:18793/v1/models
 */
process.noDeprecation = true;
const http = require('http');
const { execFile } = require('child_process');

const PORT = 18793;
const TIMEOUT_MS = 120_000;

// Modeles disponibles via Gemini CLI (verifies fonctionnels)
const AVAILABLE_MODELS = [
  { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro (Reasoning)', ctx: 1048576 },
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash (Fast)', ctx: 1048576 },
  { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash (Stable)', ctx: 1048576 },
];

function cleanStderr(stderr) {
  return (stderr || '').split('\n')
    .filter(l =>
      !l.includes('DeprecationWarning') &&
      !l.includes('trace-deprecation') &&
      !l.includes('punycode') &&
      !l.includes('NODE_NO_WARNINGS') &&
      !l.includes('Loaded cached credentials') &&
      !l.includes('[ImportProcessor]') &&
      l.trim()
    )
    .join('\n').trim();
}

function callGemini(prompt, model) {
  return new Promise((resolve, reject) => {
    const args = ['-o', 'text'];
    if (model) args.push('-m', model);
    args.push(prompt);

    const cmd = process.platform === 'win32' ? 'gemini.cmd' : 'gemini';
    execFile(cmd, args, {
      timeout: TIMEOUT_MS,
      maxBuffer: 4 * 1024 * 1024,
      env: { ...process.env, NODE_NO_WARNINGS: '1' },
      shell: process.platform === 'win32',
    }, (error, stdout, stderr) => {
      const output = (stdout || '').trim();
      if (error && !output) {
        reject(new Error(cleanStderr(stderr) || error.message));
      } else {
        resolve(output);
      }
    });
  });
}

function messagesToPrompt(messages) {
  if (!messages || !messages.length) return '';
  // Concatene les messages en format conversationnel
  return messages.map(m => {
    const role = m.role === 'assistant' ? 'Assistant' : m.role === 'system' ? 'System' : 'User';
    const content = typeof m.content === 'string' ? m.content :
      (Array.isArray(m.content) ? m.content.map(c => c.text || '').join('\n') : '');
    return `${role}: ${content}`;
  }).join('\n\n');
}

function makeCompletionResponse(text, model, promptTokens) {
  return {
    id: `chatcmpl-gemini-${Date.now()}`,
    object: 'chat.completion',
    created: Math.floor(Date.now() / 1000),
    model: model || 'gemini-2.5-flash',
    choices: [{
      index: 0,
      message: { role: 'assistant', content: text },
      finish_reason: 'stop',
    }],
    usage: {
      prompt_tokens: promptTokens || 0,
      completion_tokens: Math.ceil(text.length / 4),
      total_tokens: (promptTokens || 0) + Math.ceil(text.length / 4),
    },
  };
}

function makeModelsResponse() {
  return {
    object: 'list',
    data: AVAILABLE_MODELS.map(m => ({
      id: m.id,
      object: 'model',
      created: 1700000000,
      owned_by: 'google',
    })),
  };
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString()));
      } catch (e) {
        reject(e);
      }
    });
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', '*');
  res.setHeader('Access-Control-Allow-Methods', '*');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    return res.end();
  }

  // GET /v1/models
  if (req.method === 'GET' && (req.url === '/v1/models' || req.url === '/api/v1/models')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(makeModelsResponse()));
  }

  // GET /health
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ status: 'ok', port: PORT, models: AVAILABLE_MODELS.length }));
  }

  // POST /v1/chat/completions
  if (req.method === 'POST' && (req.url === '/v1/chat/completions' || req.url === '/api/v1/chat/completions')) {
    try {
      const body = await readBody(req);
      const model = body.model || 'gemini-2.5-flash';
      const messages = body.messages || [];
      const prompt = messagesToPrompt(messages);

      if (!prompt) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ error: { message: 'Empty prompt' } }));
      }

      const text = await callGemini(prompt, model);
      const response = makeCompletionResponse(text, model, Math.ceil(prompt.length / 4));

      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify(response));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({
        error: { message: err.message, type: 'server_error' }
      }));
    }
  }

  // POST /v1/chat (LM Studio format)
  if (req.method === 'POST' && (req.url === '/v1/chat' || req.url === '/api/v1/chat')) {
    try {
      const body = await readBody(req);
      const model = body.model || 'gemini-2.5-flash';
      const input = body.input || '';
      const prompt = typeof input === 'string' ? input : JSON.stringify(input);

      if (!prompt) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ error: { message: 'Empty input' } }));
      }

      const text = await callGemini(prompt, model);
      // LM Studio response format
      const response = {
        id: `resp-gemini-${Date.now()}`,
        output: [{ type: 'message', content: [{ type: 'output_text', text }] }],
        model,
        usage: { input_tokens: Math.ceil(prompt.length / 4), output_tokens: Math.ceil(text.length / 4) },
      };

      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify(response));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ error: { message: err.message } }));
    }
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[GEMINI-PROXY] OpenAI-compatible server on http://127.0.0.1:${PORT}`);
  console.log(`[GEMINI-PROXY] Models: ${AVAILABLE_MODELS.map(m => m.id).join(', ')}`);
  console.log(`[GEMINI-PROXY] Endpoints: /v1/chat/completions, /v1/chat, /v1/models, /health`);
});
