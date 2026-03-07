export type Page = 'dashboard' | 'chat' | 'trading' | 'voice' | 'lmstudio' | 'settings' | 'dictionary' | 'pipelines' | 'toolbox' | 'logs' | 'terminal' | 'orchestrator' | 'memory' | 'metrics' | 'alerts' | 'workflows' | 'health' | 'resources' | 'scheduler' | 'services' | 'notifications' | 'queue' | 'gateway' | 'infra' | 'mesh' | 'automation' | 'processes' | 'snapshots' | 'system' | 'browser';

/** Extract error message from unknown catch value. */
export function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
