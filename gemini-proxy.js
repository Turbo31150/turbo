#!/usr/bin/env node
/**
 * gemini-proxy.js — Wrapper Gemini CLI pour Claude Code MAO
 *
 * Usage:
 *   node gemini-proxy.js "ton prompt ici"
 *   node gemini-proxy.js --json "ton prompt ici"
 *   node gemini-proxy.js --model gemini-2.5-pro "ton prompt"
 *   echo "prompt" | node gemini-proxy.js
 *
 * Features: timeout 2min, fallback flash→pro, filtrage warnings, mode JSON
 */

const { spawn } = require('child_process');

const TIMEOUT_MS = 120_000;
const MODELS = ['gemini-2.5-pro', 'gemini-2.5-flash'];

const args = process.argv.slice(2);
const jsonMode = args.includes('--json');
const modelIdx = args.indexOf('--model');
const requestedModel = modelIdx !== -1 ? args[modelIdx + 1] : null;
const prompt = args
  .filter((a, i) => a !== '--json' && a !== '--model' && (modelIdx === -1 || i !== modelIdx + 1))
  .join(' ');

if (!prompt && process.stdin.isTTY) {
  console.error('Usage: node gemini-proxy.js [--json] [--model MODEL] "votre prompt"');
  process.exit(1);
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString().trim();
}

async function callGemini(text, model) {
  return new Promise((resolve, reject) => {
    const geminiArgs = ['-o', 'text'];
    if (model) geminiArgs.push('-m', model);
    geminiArgs.push(text);

    const child = spawn('gemini', geminiArgs, {
      stdio: ['ignore', 'pipe', 'pipe'],
      timeout: TIMEOUT_MS,
      shell: true,
    });

    let stdout = '', stderr = '';
    child.stdout.on('data', d => stdout += d);
    child.stderr.on('data', d => stderr += d);

    const timer = setTimeout(() => {
      child.kill('SIGTERM');
      reject(new Error(`TIMEOUT: Gemini n'a pas repondu en ${TIMEOUT_MS / 1000}s`));
    }, TIMEOUT_MS);

    child.on('close', code => {
      clearTimeout(timer);
      // Filtrer les warnings Node.js (punycode) et les erreurs d'extension
      const cleanStderr = stderr.split('\n')
        .filter(l =>
          !l.includes('DeprecationWarning') &&
          !l.includes('trace-deprecation') &&
          !l.includes('[ImportProcessor]') &&
          l.trim()
        )
        .join('\n').trim();

      if (code !== 0 && !stdout.trim()) {
        const is429 = stderr.includes('429') || stderr.includes('RESOURCE_EXHAUSTED');
        reject(Object.assign(new Error(cleanStderr || `Exit code ${code}`), { is429 }));
      } else {
        resolve({ text: stdout.trim(), model: model || 'default' });
      }
    });

    child.on('error', reject);
  });
}

async function callWithFallback(text) {
  const modelsToTry = requestedModel ? [requestedModel] : MODELS;

  for (const model of modelsToTry) {
    try {
      return await callGemini(text, model);
    } catch (err) {
      if (err.is429 && modelsToTry.indexOf(model) < modelsToTry.length - 1) {
        // Rate limited, try next model
        continue;
      }
      throw err;
    }
  }
}

(async () => {
  try {
    const input = prompt || await readStdin();
    if (!input) {
      console.error('Erreur: prompt vide');
      process.exit(1);
    }

    const result = await callWithFallback(input);

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
