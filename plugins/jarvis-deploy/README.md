# jarvis-deploy

JARVIS deployment plugin for Claude Code. Automates git commit, push, and Telegram notification.

## Commands

- `/deploy` — Stage review, auto-commit message, push, Telegram notify
- `/deploy-status` — Show last commit, branch, diff stat

## Hook

- **Stop** — Reminds about uncommitted changes at end of session

## Setup

```bash
claude --plugin-dir F:/BUREAU/turbo/plugins/jarvis-deploy
```

## Requirements

- Git configured with remote `origin`
- `TELEGRAM_TOKEN` and `TELEGRAM_CHAT` in `F:/BUREAU/turbo/.env`
