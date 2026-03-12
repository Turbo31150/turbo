#!/usr/bin/env node
/**
 * claude-proxy.js — Wrapper Claude Code CLI pour JARVIS MAO v10.3
 *
 * Usage:
 *   node claude-proxy.js "ton prompt ici"
 *   node claude-proxy.js --json "ton prompt ici"
 *   node claude-proxy.js --model opus "ton prompt"
 *   node claude-proxy.js --system "Tu es un expert Python" "ton prompt"
 *   echo "prompt" | node claude-proxy.js
 *
 * Features:
 *   - Sonnet (default) + fallback Haiku
 *   - Mode JSON structuré via --output-format json
 *   - Timeout 2min, filtrage warnings, mode JSON
 *   - Health check: node claude-proxy.js --ping
 *   - Budget cap: --budget 0.50 (USD, default 1.00)
 *   - Skip permissions pour mode non-interactif
 *   - Env sanitisé (suppression CLAUDE* vars pour isolation subprocess)
 */

process.noDeprecation = true;
const { spawn } = require('child_process');

const TIMEOUT_MS = 120_000;
const DEFAULT_BUDGET = '1.00';
const MODELS = [
  'opus',
  'sonnet',
  'haiku',
];

// ── Parse args ──────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const jsonMode = args.includes('--json');
const pingMode = args.includes('--ping');
const modelIdx = args.indexOf('--model');
const requestedModel = modelIdx !== -1 ? args[modelIdx + 1] : null;
const systemIdx = args.indexOf('--system');
const systemPrompt = systemIdx !== -1 ? args[systemIdx + 1] : null;
const budgetIdx = args.indexOf('--budget');
const budget = budgetIdx !== -1 ? args[budgetIdx + 1] : DEFAULT_BUDGET;

const skipFlags = new Set(['--json', '--ping', '--model', '--system', '--budget']);
const prompt = args
  .filter((a, i) => {
    if (skipFlags.has(a)) return false;
    // Skip values following flags that take arguments
    if (modelIdx !== -1 && i === modelIdx + 1) return false;
    if (systemIdx !== -1 && i === systemIdx + 1) return false;
    if (budgetIdx !== -1 && i === budgetIdx + 1) return false;
    return true;
  })
  .join(' ');

if (!prompt && !pingMode && process.stdin.isTTY) {
  console.error('Usage: node claude-proxy.js [--json] [--ping] [--model MODEL] [--system SYSTEM_PROMPT] [--budget USD] "votre prompt"');
  process.exit(1);
}

// ── Stdin reader ────────────────────────────────────────────────────────
async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString().trim();
}

// ── Clean stderr (remove Node warnings, debug noise) ────────────────────
function cleanStderr(stderr) {
  return (stderr || '').split('\n')
    .filter(l =>
      !l.includes('DeprecationWarning') &&
      !l.includes('trace-deprecation') &&
      !l.includes('ExperimentalWarning') &&
      !l.includes('NODE_NO_WARNINGS') &&
      !l.includes('punycode') &&
      !l.includes('[DEBUG]') &&
      !l.includes('Compressing') &&
      l.trim()
    )
    .join('\n').trim();
}

// ── Call Claude CLI (spawn-based for Windows compatibility) ──────────────
async function callClaude(text, model, useJsonOutput) {
  return new Promise((resolve, reject) => {
    const claudeArgs = [
      '-p',                           // print mode (non-interactive)
      '--dangerously-skip-permissions', // no permission prompts
      '--no-session-persistence',      // don't save session
      '--disable-slash-commands',      // skip plugins/skills loading
      '--max-budget-usd', budget,
    ];

    if (useJsonOutput) {
      claudeArgs.push('--output-format', 'json');
    }

    if (model) claudeArgs.push('--model', model);
    if (systemPrompt) claudeArgs.push('--system-prompt', systemPrompt);

    claudeArgs.push(text);

    // Build sanitized env: remove ALL CLAUDE* vars to prevent nested session detection
    const cleanEnv = { ...process.env, NODE_NO_WARNINGS: '1' };
    Object.keys(cleanEnv).filter(k => k.startsWith('CLAUDE')).forEach(k => delete cleanEnv[k]);

    const child = spawn('claude', claudeArgs, {
      env: cleanEnv,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', d => { stdout += d.toString(); });
    child.stderr.on('data', d => { stderr += d.toString(); });

    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`Timeout after ${TIMEOUT_MS / 1000}s`));
    }, TIMEOUT_MS);

    child.on('error', err => {
      clearTimeout(timer);
      reject(err);
    });

    child.on('close', code => {
      clearTimeout(timer);
      const cleanErr = cleanStderr(stderr);
      const output = (stdout || '').trim();

      if (code !== 0 && !output) {
        const is429 = stderr.includes('429') || stderr.includes('rate_limit') || stderr.includes('overloaded');
        const isOverloaded = stderr.includes('529') || stderr.includes('overloaded');
        reject(Object.assign(new Error(cleanErr || `Exit code ${code}`), { is429, isOverloaded }));
      } else {
        if (useJsonOutput && output) {
          try {
            const parsed = JSON.parse(output);
            const response = parsed.result || parsed.response || parsed.text || output;
            resolve({ text: response, model: model || 'sonnet', raw: parsed });
          } catch {
            resolve({ text: output, model: model || 'sonnet', raw: null });
          }
        } else {
          resolve({ text: output, model: model || 'sonnet', raw: null });
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
      return await callClaude(text, model, useJsonOutput);
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
    const result = await callClaude('Reponds uniquement: OK', 'haiku', false);
    const ok = result.text.toLowerCase().includes('ok');
    if (jsonMode) {
      console.log(JSON.stringify({ agent: 'CLAUDE', status: ok ? 'ok' : 'degraded', response: result.text }));
    } else {
      console.log(ok ? 'CLAUDE OK' : `CLAUDE DEGRADED: ${result.text.slice(0, 100)}`);
    }
    process.exit(0);
  } catch (err) {
    if (jsonMode) {
      console.log(JSON.stringify({ agent: 'CLAUDE', status: 'error', error: err.message }));
    } else {
      console.error(`CLAUDE OFFLINE: ${err.message}`);
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
        agent: 'CLAUDE',
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
        agent: 'CLAUDE',
        status: 'error',
        error: err.message,
      }));
    } else {
      console.error(`[CLAUDE ERROR] ${err.message}`);
    }
    process.exit(1);
  }
})();
