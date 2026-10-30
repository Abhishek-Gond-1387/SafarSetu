/**
 * SafarSetu Progressive Web App (PWA) Controller.
 * Manages Service Worker lifecycle and Browser Install Prompts (Android, Chrome, Edge, Safari iOS).
 */

export interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: 'accepted' | 'dismissed';
    platform: string;
  }>;
  prompt(): Promise<void>;
}

export interface PWAState {
  isInstallable: boolean;
  isInstalled: boolean;
  isIOS: boolean;
  isOffline: boolean;
}

let deferredPrompt: BeforeInstallPromptEvent | null = null;
const stateListeners = new Set<(state: PWAState) => void>();

function checkIsInstalled(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    (window.navigator as any).standalone === true ||
    document.referrer.includes('android-app://')
  );
}

function checkIsIOS(): boolean {
  if (typeof window === 'undefined') return false;
  const userAgent = window.navigator.userAgent.toLowerCase();
  return /iphone|ipad|ipod/.test(userAgent) && !(window as any).MSStream;
}

const currentState: PWAState = {
  isInstallable: false,
  isInstalled: false,
  isIOS: false,
  isOffline: false,
};

function notifyListeners() {
  stateListeners.forEach((listener) => {
    try {
      listener({ ...currentState });
    } catch (e) {
      console.warn('[PWA] Listener error:', e);
    }
  });
}

/**
 * Register Service Worker & Install Event Handlers
 */
export function registerPWA(): void {
  if (typeof window === 'undefined') return;

  currentState.isInstalled = checkIsInstalled();
  currentState.isIOS = checkIsIOS();
  currentState.isOffline = !navigator.onLine;

  // Track online / offline transitions
  window.addEventListener('online', () => {
    currentState.isOffline = false;
    notifyListeners();
  });

  window.addEventListener('offline', () => {
    currentState.isOffline = true;
    notifyListeners();
  });

  // Track native beforeinstallprompt (Chrome, Android, Edge, Samsung Browser)
  window.addEventListener('beforeinstallprompt', (e: Event) => {
    e.preventDefault(); // Prevent standard browser mini-infobar
    deferredPrompt = e as BeforeInstallPromptEvent;
    currentState.isInstallable = true;
    console.log('[SafarSetu PWA] Install prompt captured and ready for user trigger.');
    notifyListeners();
  });

  // Track successful installation
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    currentState.isInstallable = false;
    currentState.isInstalled = true;
    console.log('[SafarSetu PWA] SafarSetu App successfully installed!');
    notifyListeners();
  });

  // Register the service worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/sw.js', { scope: '/' })
        .then((reg) => {
          console.log('[SafarSetu PWA] Service Worker registered with scope:', reg.scope);

          // Listen for updates
          reg.onupdatefound = () => {
            const installingWorker = reg.installing;
            if (installingWorker) {
              installingWorker.onstatechange = () => {
                if (installingWorker.state === 'installed' && navigator.serviceWorker.controller) {
                  console.log('[SafarSetu PWA] New version available! Reloading cache.');
                }
              };
            }
          };
        })
        .catch((err) => {
          console.error('[SafarSetu PWA] Service Worker registration failed:', err);
        });
    });
  }
}

/**
 * Trigger the native PWA Installation prompt or provide iOS instructions
 */
export async function promptPWAInstall(): Promise<'accepted' | 'dismissed' | 'ios' | 'unsupported'> {
  if (currentState.isIOS && !currentState.isInstalled) {
    return 'ios';
  }

  if (!deferredPrompt) {
    console.log('[SafarSetu PWA] No deferred prompt available.');
    return 'unsupported';
  }

  try {
    await deferredPrompt.prompt();
    const choiceResult = await deferredPrompt.userChoice;
    console.log('[SafarSetu PWA] User install choice:', choiceResult.outcome);

    if (choiceResult.outcome === 'accepted') {
      deferredPrompt = null;
      currentState.isInstallable = false;
      currentState.isInstalled = true;
      notifyListeners();
      return 'accepted';
    } else {
      return 'dismissed';
    }
  } catch (err) {
    console.error('[SafarSetu PWA] Error displaying install prompt:', err);
    return 'unsupported';
  }
}

/**
 * Subscribe to PWA state changes (e.g. installability, online/offline)
 */
export function usePWAState(callback: (state: PWAState) => void): () => void {
  stateListeners.add(callback);
  callback({ ...currentState }); // Initial callback

  return () => {
    stateListeners.delete(callback);
  };
}

export function getPWAState(): PWAState {
  return { ...currentState };
}

