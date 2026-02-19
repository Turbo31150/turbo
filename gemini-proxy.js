#!/usr/bin/env node
/**
 * gemini-proxy.js — Wrapper Gemini CLI pour JARVIS MAO v10.3
 *
 * Usage:
 *   node gemini-proxy.js "ton prompt ici"
 *   node gemini-proxy.js --json "ton prompt ici"
 *   node gemini-proxy.js --model gemini-3-pro "ton prompt"
 *   echo "prompt" | node gemini-proxy.js
 *
 * Features:
 *   - Gemini 3 Pro/Flash + fallback Gemini 2.5
 *   - --output-format json natif pour structured output
 *   - Timeout 2min, filtrage warnings, mode JSON
 *   - Health check: node gemini-proxy.js --ping
 */

process.noDeprecation = true;
const { execFile } = require('child_process');

const TIMEOUT_MS = 120_000;
const MODELS = [
  'gemini-3-pro',
  'gemini-3-flash',
  'gemini-2.5-pro',
  'gemini-2.5-flash',
];

// ── Parse args ──────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const jsonMode = args.includes('--json');
const pingMode = args.includes('--ping');
const modelIdx = args.indexOf('--model');
const requestedModel = modelIdx !== -1 ? args[modelIdx + 1] : null;
const prompt = args
  .filter((a, i) =>
    a !== '--json' && a !== '--ping' && a !== '--model' &&
    (modelIdx === -1 || i !== modelIdx + 1)
  )
  .join(' ');

if (!prompt && !pingMode && process.stdin.isTTY) {
  console.error('Usage: node gemini-proxy.js [--json] [--ping] [--model MODEL] "votre prompt"');
  process.exit(1);
}

// ── Stdin reader ────────────────────────────────────────────────────────
async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString().trim();
}

// ── Clean stderr (remove Node warnings, ImportProcessor noise) ──────────
function cleanStderr(stderr) {
  return (stderr || '').split('\n')
    .filter(l =>
      !l.includes('DeprecationWarning') &&
      !l.includes('trace-deprecation') &&
      !l.includes('[ImportProcessor]') &&
      !l.includes('punycode') &&
      !l.includes('NODE_NO_WARNINGS') &&
      !l.includes('Loaded cached credentials') &&
      l.trim()
    )
    .join('\n').trim();
}

// ── Call Gemini CLI ─────────────────────────────────────────────────────
async function callGemini(text, model, useJsonOutput) {
  return new Promise((resolve, reject) => {
    const geminiArgs = [];

    if (useJsonOutput) {
      geminiArgs.push('--output-format', 'json');
    } else {
      geminiArgs.push('-o', 'text');
    }

    if (model) geminiArgs.push('-m', model);
    geminiArgs.push(text);

    const child = execFile('gemini', geminiArgs, {
      timeout: TIMEOUT_MS,
      shell: true,
      maxBuffer: 2 * 1024 * 1024,
      env: { ...process.env, NODE_NO_WARNINGS: '1' },
    }, (error, stdout, stderr) => {
      const cleanErr = cleanStderr(stderr);
      const output = (stdout || '').trim();

      if (error && !output) {
        const is429 = (stderr || '').includes('429') || (stderr || '').includes('RESOURCE_EXHAUSTED');
        const isOverloaded = (stderr || '').includes('503') || (stderr || '').includes('UNAVAILABLE');
        reject(Object.assign(new Error(cleanErr || error.message), { is429, isOverloaded }));
      } else {
        // Parse JSON output if requested
        if (useJsonOutput && output) {
          try {
            const parsed = JSON.parse(output);
            const response = parsed.response || parsed.text || output;
            resolve({ text: response, model: model || 'auto', raw: parsed });
          } catch {
            resolve({ text: output, model: model || 'auto', raw: null });
          }
        } else {
          resolve({ text: output, model: model || 'auto', raw: null });
        }
      }
    });
  });
}

// ── Call with fallback chain ────────────────────────────────────────────
async function callWithFallback(text, useJsonOutput) {
  const modelsToTry = requestedModel ? [requestedModel] : MODELS;
  let lastError = null;

  for (const model of modelsToTry) {
    try {
      return await callGemini(text, model, useJsonOutput);
    } catch (err) {
      lastError = err;
      // Rate limited or overloaded: try next model
      if ((err.is429 || err.isOverloaded) && modelsToTry.indexOf(model) < modelsToTry.length - 1) {
        continue;
      }
      // Last model or non-retryable error
      if (modelsToTry.indexOf(model) === modelsToTry.length - 1) {
        throw err;
      }
    }
  }
  throw lastError;
}

// ── Ping / Health check ─────────────────────────────────────────────────
async function ping() {
  try {
    const result = await callGemini('Reponds uniquement: OK', null, false);
    const ok = result.text.toLowerCase().includes('ok');
    if (jsonMode) {
      console.log(JSON.stringify({ agent: 'GEMINI', status: ok ? 'ok' : 'degraded', response: result.text }));
    } else {
      console.log(ok ? 'GEMINI OK' : `GEMINI DEGRADED: ${result.text.slice(0, 100)}`);
    }
    process.exit(0);
  } catch (err) {
    if (jsonMode) {
      console.log(JSON.stringify({ agent: 'GEMINI', status: 'error', error: err.message }));
    } else {
      console.error(`GEMINI OFFLINE: ${err.message}`);
    }
    process.exit(1);
  }
}

// ── Main ────────────────────────────────────────────────────────────────
(async () => {
  if (pingMode) return ping();

  try {
    const input = prompt || await readStdin();
    if (!input) {
      console.error('Erreur: prompt vide');
      process.exit(1);
    }

    const result = await callWithFallback(input, jsonMode);

    if (jsonMode) {
      console.log(JSON.stringify({
        agent: 'GEMINI',
        model: result.model,
        status: 'ok',
        response: result.text,
      }));
    } else {
      console.log(result.text);
    }
    process.exit(0);
  } catch (err) {
    if (jsonMode) {
      console.log(JSON.stringify({
        agent: 'GEMINI',
        status: 'error',
        error: err.message,
      }));
    } else {
      console.error(`[GEMINI ERROR] ${err.message}`);
    }
    process.exit(1);
  }
})();
