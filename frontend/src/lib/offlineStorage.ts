/**
 * SafarSetu Offline-First Journey Storage Manager.
 *
 * Automatically caches the commuter's selected route, step-by-step instructions,
 * interchange stations, and emergency contacts so they remain accessible underground
 * on the Delhi Metro even with 0 bars of internet connectivity.
 */
import { useEffect, useState } from 'react';
import { Journey, PlanRouteParams } from './api';

const ACTIVE_JOURNEY_KEY = 'safarsetu_active_journey_v1';
const EMERGENCY_CONTACTS_KEY = 'safarsetu_offline_emergency_contacts';

export interface OfflineStoredJourney {
  savedAt: string;
  params: PlanRouteParams | null;
  journey: Journey;
}

export const OfflineStorage = {
  /**
   * Save selected journey to localStorage for offline preservation.
   */
  saveActiveJourney(journey: Journey, params?: PlanRouteParams | null): void {
    try {
      const payload: OfflineStoredJourney = {
        savedAt: new Date().toISOString(),
        params: params || null,
        journey,
      };
      localStorage.setItem(ACTIVE_JOURNEY_KEY, JSON.stringify(payload));
    } catch (e) {
      console.warn('Failed to save active journey for offline access:', e);
    }
  },

  /**
   * Retrieve active journey stored offline.
   */
  getActiveJourney(): OfflineStoredJourney | null {
    try {
      const data = localStorage.getItem(ACTIVE_JOURNEY_KEY);
      if (!data) return null;
      return JSON.parse(data) as OfflineStoredJourney;
    } catch (e) {
      console.warn('Failed to parse offline journey data:', e);
      return null;
    }
  },

  /**
   * Clear offline journey once completed or dismissed.
   */
  clearActiveJourney(): void {
    try {
      localStorage.removeItem(ACTIVE_JOURNEY_KEY);
    } catch (e) {
      console.warn('Failed to clear offline journey:', e);
    }
  },

  /**
   * Get default Delhi/NCR emergency helpline numbers for offline dialer.
   */
  getEmergencyHelplines() {
    return [
      { name: 'National Emergency / Delhi Police', number: '112', type: 'police' },
      { name: "Women's Safety Helpline", number: '1091', type: 'women_safety' },
      { name: 'DMRC Metro 24x7 Helpline', number: '155370', type: 'metro' },
      { name: 'Ambulance / Medical Emergency', number: '102', type: 'medical' },
    ];
  },
};

/**
 * React Hook that monitors online / offline connectivity state in real time.
 */
export function useOnlineStatus(): boolean {
  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  );

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return isOnline;
}
