export type Page = 'dashboard' | 'chat' | 'trading' | 'voice' | 'lmstudio' | 'settings' | 'dictionary' | 'pipelines' | 'toolbox' | 'logs';

/** Extract error message from unknown catch value. */
export function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
