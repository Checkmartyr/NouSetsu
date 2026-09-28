const DESKTOP_BACKEND_URL = 'http://127.0.0.1:5174';

export function isTauriDesktopRuntime(): boolean {
  if (typeof window === 'undefined') return false;

  return (
    '__TAURI_INTERNALS__' in window ||
    '__TAURI__' in window ||
    window.location.protocol === 'tauri:' ||
    window.location.hostname === 'tauri.localhost'
  );
}

export function getApiBaseUrl(
  isDesktop = isTauriDesktopRuntime()
): string {
  if (typeof window === 'undefined') return '';

  const localBackendOrigin =
    ['127.0.0.1', 'localhost'].includes(window.location.hostname) &&
    window.location.port === '5174';

  return isDesktop || localBackendOrigin ? DESKTOP_BACKEND_URL : '';
}

export const API_BASE = getApiBaseUrl();
