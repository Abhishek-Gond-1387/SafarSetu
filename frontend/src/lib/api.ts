/**
 * SafarSetu API Client.
 *
 * Interacts with FastAPI backend for transit routing, stops search, health status,
 * and authenticated user profile/saved-journeys operations.
 */
import { supabaseAuth } from './supabase';

const getApiBase = () => {
  if (typeof (globalThis as any).process !== 'undefined' && (globalThis as any).process?.env?.NEXT_PUBLIC_API_BASE_URL) {
    return (globalThis as any).process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  if (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE_URL) {
    return (import.meta as any).env.VITE_API_BASE_URL;
  }
  if (typeof window !== 'undefined' && (window.location.port === '5173' || window.location.port === '5174')) {
    return 'http://127.0.0.1:8000/api/v1';
  }
  return '/api/v1';
};

const API_BASE = getApiBase();

async function fetchJSON<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const session = supabaseAuth.getSession();
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (session?.accessToken) {
    headers.set('Authorization', `Bearer ${session.accessToken}`);
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    const errorMsg =
      errorBody.detail ||
      (typeof errorBody.message === 'string' ? errorBody.message : `HTTP ${res.status}: ${res.statusText}`);
    throw new Error(errorMsg);
  }

  if (res.status === 204) {
    return null as any;
  }
  return res.json();
}

export interface StopItem {
  stop_id: string;
  stop_name: string;
  stop_lat: number;
  stop_lon: number;
  stop_code?: string;
  stop_desc?: string;
  location_type?: number;
  source_id?: string;
}

export interface StopsSearchResponse {
  total: number;
  page: number;
  page_size: number;
  results: StopItem[];
}

export interface LegStopDetail {
  stop_id: string;
  stop_name: string;
  lat: number;
  lon: number;
  is_board: boolean;
  is_alight: boolean;
  mode: string;
}

export interface JourneyLeg {
  mode: 'transit' | 'walking' | 'bus' | 'walk' | 'metro';
  from_stop_id: string;
  to_stop_id: string;
  from_stop_name: string;
  to_stop_name: string;
  from_stop_lat?: number | null;
  from_stop_lon?: number | null;
  to_stop_lat?: number | null;
  to_stop_lon?: number | null;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  route_id?: string;
  route_short_name?: string;
  route_long_name?: string;
  trip_id?: string;
  headsign?: string;
  distance_meters?: number;
  distance_type?: string;
  fare_inr?: number | null;
  fare_note?: string;
  intermediate_stops?: string[];
  source_id?: string;
  path_coordinates?: [number, number][];
  stops_detail?: LegStopDetail[];
}

export interface MetroLineStatus {
  line_name: string;
  line_code: string;
  color_hex: string;
  text_color_hex: string;
  terminals: string;
  status: string;
  headway_peak: string;
  headway_offpeak: string;
  operating_hours: string;
  total_stations: number;
  interchanges: string[];
  live_advisory: string;
  last_updated: string;
}

export interface MetroNetworkStatusResponse {
  agency: string;
  network_health: string;
  active_lines_count: number;
  lines: MetroLineStatus[];
  system_advisory: string;
  timestamp: string;
}

export interface Journey {
  departure_time: string;
  arrival_time: string;
  total_duration_minutes: number;
  total_walk_meters: number;
  num_transfers: number;
  initial_wait_minutes: number;
  fare_inr?: number | null;
  fare_complete: boolean;
  fare_note?: string;
  rank_criterion: 'fastest' | 'cheapest' | 'balanced';
  legs: JourneyLeg[];
  warnings: string[];
  data_sources: string[];
}

export interface RoutePlanResponse {
  origin_stop_id: string;
  destination_stop_id: string;
  departure_date: string;
  requested_time: string;
  criterion: string;
  journeys: Journey[];
  data_freshness_warnings: string[];
  calendar_validity_note?: string;
  no_route_reason?: string;
}

export interface PlanRouteParams {
  origin_stop_id: string;
  destination_stop_id: string;
  departure_date: string;
  departure_time: string;
  criterion?: 'fastest' | 'cheapest' | 'balanced';
  max_transfers?: number;
  max_walk_meters?: number;
  mode_preference?: 'all' | 'metro' | 'bus' | 'multimodal';
}

export interface ModeOption {
  mode_id: 'metro' | 'bus' | 'multimodal' | 'auto' | 'cab';
  title: string;
  icon: string;
  available: boolean;
  description: string;
  estimated_duration_minutes: number;
  estimated_distance_km: number;
  fare_inr: number;
  fare_breakdown: string;
  optimization_tags: string[];
  recommended_origin_stop?: StopItem | null;
  recommended_destination_stop?: StopItem | null;
  candidate_origin_stops: StopItem[];
  candidate_destination_stops: StopItem[];
  lines_or_routes: string[];
}

export interface ModeExploreResponse {
  origin_stop?: StopItem | null;
  destination_stop: StopItem;
  straight_line_distance_km: number;
  road_distance_km: number;
  modes: ModeOption[];
}

export interface DataSourceItem {
  source_id: string;
  label: string;
  status: string;
  stops_count?: number;
  routes_count?: number;
  trips_count?: number;
  feed_start_date?: string;
  feed_end_date?: string;
  warnings: string[];
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  version: string;
  project_name?: string;
  environment?: string;
  data_sources?: DataSourceItem[];
  sources?: DataSourceItem[];
  graph_nodes: number;
  graph_edges: number;
  realtime?: {
    enabled: boolean;
    api_key_configured: boolean;
    last_poll_status?: string;
    cached_vehicles_count: number;
    feed_freshness: string;
    live_tracking_verified: boolean;
  };
}

export interface RealtimeStatusResponse {
  enabled: boolean;
  api_key_configured: boolean;
  last_poll_status?: string;
  last_successful_fetch?: string;
  last_feed_timestamp?: string;
  cached_vehicles_count: number;
  rejected_entities_count: number;
  feed_freshness: string;
  live_tracking_verified: boolean;
  error_category?: string;
  error_message?: string;
}

export interface SavedJourney {
  id: string;
  journey_name: string;
  origin_stop_id: string;
  destination_stop_id: string;
  departure_time_preference?: string;
  ranking_criterion_preference?: string;
  created_at: string;
}

export interface UserPreferences {
  default_ranking_criterion: string;
  preferred_language: string;
  max_walking_distance_meters?: number;
  wheelchair_accessible: boolean;
}

export interface NearbyStopItem extends StopItem {
  distance_meters: number;
  distance_type?: string;
}

export interface NearbyStopsResponse {
  query_lat: number;
  query_lon: number;
  radius_meters: number;
  distance_note?: string;
  results: NearbyStopItem[];
}

export interface NearestStationDetail {
  stop_id: string;
  stop_name: string;
  stop_lat: number;
  stop_lon: number;
  type: 'metro' | 'bus' | 'auto_stand';
  distance_meters: number;
  walk_minutes: number;
  lines: string[];
  directions_text: string;
}

export interface LostAssistanceRequest {
  user_lat: number;
  user_lon: number;
  destination_stop_id?: string;
  destination_name?: string;
  preferred_mode?: string;
}

export interface LostAssistanceResponse {
  user_lat: number;
  user_lon: number;
  nearest_metro: NearestStationDetail | null;
  nearest_bus_stop: NearestStationDetail | null;
  nearest_station_overall: NearestStationDetail;
  auto_rickshaw_fare_estimate_inr: number;
  auto_pickup_instructions: string;
  rerouted_plan: RoutePlanResponse | null;
  reassuring_message: string;
  spoken_guidance: {
    en?: string;
    hi?: string;
    hinglish?: string;
  };
}

export interface VoiceStepGuidance {
  step_number: number;
  total_steps: number;
  step_type: 'walk' | 'board_metro' | 'board_bus' | 'in_transit' | 'transfer' | 'alight' | 'destination';
  spoken_instruction: string;
  display_instruction: string;
  stop_name: string;
  line_name?: string;
  headsign?: string;
  duration_minutes?: number;
  distance_meters?: number;
  next_stop_name?: string;
  fare_inr?: number;
}

export interface VoiceQueryRequest {
  query: string;
  language?: string;
  target_language?: string;
  session_id?: string;
  current_journey?: Journey | null;
  current_leg_index?: number | null;
  user_lat?: number | null;
  user_lon?: number | null;
}

export interface VoiceQueryResponse {
  success: boolean;
  transcript: string;
  detected_language: string;
  response_language: string;
  intent: string;
  spoken_text: string;
  display_text: string;
  action?: 'NAVIGATE' | 'REROUTE' | 'STEP_GUIDANCE' | 'SET_FILTER' | 'NONE';
  entities?: Record<string, any>;
  planned_route?: RoutePlanResponse | null;
  step_guidance?: VoiceStepGuidance | null;
  suggested_followups: string[];
}

export interface VoiceLanguageItem {
  code: string;
  name: string;
  native_name: string;
  locale: string;
  speech_supported: boolean;
}

export interface VoiceLanguagesResponse {
  supported_languages: VoiceLanguageItem[];
  default: string;
}

export const SafarSetuAPI = {
  // Transit Search & Routing
  async searchStops(query: string, pageSize: number = 10): Promise<StopsSearchResponse> {
    const encoded = encodeURIComponent(query.trim());
    return fetchJSON<StopsSearchResponse>(`/stops?query=${encoded}&page_size=${pageSize}`);
  },

  async getNearbyStops(
    lat: number,
    lon: number,
    radiusMeters: number = 3000,
    limit: number = 10
  ): Promise<NearbyStopsResponse> {
    return fetchJSON<NearbyStopsResponse>(
      `/stops/nearby?lat=${lat}&lon=${lon}&radius_meters=${radiusMeters}&limit=${limit}`
    );
  },

  async planRoute(params: PlanRouteParams): Promise<RoutePlanResponse> {
    return fetchJSON<RoutePlanResponse>('/routes/plan', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async getLostAssistance(req: LostAssistanceRequest): Promise<LostAssistanceResponse> {
    return fetchJSON<LostAssistanceResponse>('/routes/lost-assistance', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async exploreModes(params: {
    destination_stop_id: string;
    origin_stop_id?: string;
    departure_date?: string;
    departure_time?: string;
  }): Promise<ModeExploreResponse> {
    return fetchJSON<ModeExploreResponse>('/routes/modes', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async getHealth(): Promise<HealthResponse> {
    return fetchJSON<HealthResponse>('/health');
  },

  async getRealtimeStatus(): Promise<RealtimeStatusResponse> {
    return fetchJSON<RealtimeStatusResponse>('/realtime/status');
  },

  async getMetroRealtimeStatus(): Promise<MetroNetworkStatusResponse> {
    return fetchJSON<MetroNetworkStatusResponse>('/realtime/metro');
  },

  async getVehicles(params: { route_id?: string; limit?: number } = {}): Promise<{
    total: number;
    feed_freshness: string;
    results: Array<{
      vehicle_id: string;
      latitude: number;
      longitude: number;
      route_id?: string;
      route_long_name?: string;
      speed_kmh?: number;
    }>;
  }> {
    const q = new URLSearchParams();
    if (params.route_id) q.set('route_id', params.route_id);
    if (params.limit) q.set('limit', String(params.limit));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return fetchJSON(`/realtime/vehicles${qs}`);
  },

  // User Profile & Preferences
  async getCurrentUser() {
    return fetchJSON('/users/me');
  },

  async updateProfile(data: { display_name?: string; preferred_language?: string }) {
    return fetchJSON('/users/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async getPreferences(): Promise<UserPreferences> {
    return fetchJSON<UserPreferences>('/users/me/preferences');
  },

  async updatePreferences(data: Partial<UserPreferences>) {
    return fetchJSON('/users/me/preferences', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  // Saved Journeys
  async getSavedJourneys(limit = 50, offset = 0): Promise<{ total: number; results: SavedJourney[] }> {
    return fetchJSON(`/users/me/saved-journeys?limit=${limit}&offset=${offset}`);
  },

  async saveJourney(data: {
    journey_name: string;
    origin_stop_id: string;
    destination_stop_id: string;
    departure_time_preference?: string;
    ranking_criterion_preference?: string;
  }): Promise<SavedJourney> {
    return fetchJSON('/users/me/saved-journeys', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async deleteSavedJourney(journeyId: string): Promise<void> {
    return fetchJSON(`/users/me/saved-journeys/${journeyId}`, {
      method: 'DELETE',
    });
  },

  // Feedback
  async submitFeedback(data: { category: string; description: string }): Promise<{ message: string; feedback_id: string }> {
    return fetchJSON('/users/feedback', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /**
   * Permanently delete the authenticated user's account.
   * The backend uses the Supabase service-role key server-side to remove the auth user.
   * The service-role key is NEVER sent to or exposed in the browser.
   */
  async deleteAccount(): Promise<void> {
    return fetchJSON('/users/me', {
      method: 'DELETE',
    });
  },

  // Multilingual Voice Assistant
  async sendVoiceQuery(params: VoiceQueryRequest): Promise<VoiceQueryResponse> {
    return fetchJSON<VoiceQueryResponse>('/voice/interact', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async getVoiceStepGuidance(params: {
    journey: Journey;
    leg_index: number;
    sub_step?: string;
    target_language?: string;
  }): Promise<VoiceStepGuidance> {
    return fetchJSON<VoiceStepGuidance>('/voice/guidance', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async getVoiceLanguages(): Promise<VoiceLanguagesResponse> {
    return fetchJSON<VoiceLanguagesResponse>('/voice/languages');
  },
};
