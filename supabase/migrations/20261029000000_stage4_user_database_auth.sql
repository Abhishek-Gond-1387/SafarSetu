-- ==============================================================================
-- SafarSetu — Stage 4: User Database and Authentication Migration
-- Description: Creates user profiles, preferences, saved journeys, recent searches,
--              and feedback tables with Row Level Security (RLS) and triggers.
-- ==============================================================================

-- 1. Profiles Table
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT NULL,
    preferred_language TEXT NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en', 'hi', 'pa', 'ur')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

COMMENT ON TABLE public.profiles IS 'commuter profile data linked to Supabase auth.users';

-- 2. User Preferences Table
CREATE TABLE IF NOT EXISTS public.user_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    default_ranking_criterion TEXT NOT NULL DEFAULT 'fastest' CHECK (default_ranking_criterion IN ('fastest', 'cheapest', 'balanced')),
    preferred_language TEXT NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en', 'hi', 'pa', 'ur')),
    max_walking_distance_meters FLOAT NOT NULL DEFAULT 800.0 CHECK (max_walking_distance_meters >= 0.0 AND max_walking_distance_meters <= 5000.0),
    wheelchair_accessible BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

COMMENT ON TABLE public.user_preferences IS 'Default commuter journey planning preferences and routing constraints';

-- 3. Saved Journeys Table
CREATE TABLE IF NOT EXISTS public.saved_journeys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    journey_name TEXT NOT NULL CHECK (char_length(trim(journey_name)) >= 1 AND char_length(journey_name) <= 100),
    origin_stop_id TEXT NOT NULL,
    destination_stop_id TEXT NOT NULL,
    origin_stop_name TEXT NULL,
    destination_stop_name TEXT NULL,
    departure_time_preference TEXT NULL,
    ranking_criterion_preference TEXT NULL CHECK (ranking_criterion_preference IS NULL OR ranking_criterion_preference IN ('fastest', 'cheapest', 'balanced')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT check_distinct_stops CHECK (origin_stop_id <> destination_stop_id)
);

CREATE INDEX IF NOT EXISTS idx_saved_journeys_user_id ON public.saved_journeys(user_id);
COMMENT ON TABLE public.saved_journeys IS 'Personal bookmarked transit itineraries; validated against genuine GTFS stops';

-- 4. Recent Searches Table (with 20-item retention policy)
CREATE TABLE IF NOT EXISTS public.recent_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    origin_stop_id TEXT NOT NULL,
    destination_stop_id TEXT NOT NULL,
    origin_stop_name TEXT NULL,
    destination_stop_name TEXT NULL,
    searched_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_recent_searches_user_searched_at ON public.recent_searches(user_id, searched_at DESC);
COMMENT ON TABLE public.recent_searches IS 'Recent journey searches with bounded retention policy (max 20 records per user)';

-- 5. User Feedback Table
CREATE TABLE IF NOT EXISTS public.user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NULL REFERENCES auth.users(id) ON DELETE SET NULL,
    category TEXT NOT NULL CHECK (category IN ('schedule_inaccuracy', 'bus_delay', 'missing_stop', 'app_issue', 'safety_concern', 'general')),
    description TEXT NOT NULL CHECK (char_length(description) >= 5 AND char_length(description) <= 2000),
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'under_review', 'resolved', 'dismissed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_user_feedback_user_id ON public.user_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_status ON public.user_feedback(review_status);
COMMENT ON TABLE public.user_feedback IS 'Commuter reports; never treated as unverified transit schedule ground truth';

-- ==============================================================================
-- Triggers and Functions
-- ==============================================================================

-- Trigger to maintain updated_at timestamp
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_profiles_updated_at ON public.profiles;
CREATE TRIGGER set_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_user_preferences_updated_at ON public.user_preferences;
CREATE TRIGGER set_user_preferences_updated_at
    BEFORE UPDATE ON public.user_preferences
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_saved_journeys_updated_at ON public.saved_journeys;
CREATE TRIGGER set_saved_journeys_updated_at
    BEFORE UPDATE ON public.saved_journeys
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_user_feedback_updated_at ON public.user_feedback;
CREATE TRIGGER set_user_feedback_updated_at
    BEFORE UPDATE ON public.user_feedback
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Trigger to auto-create profile and preferences on Supabase auth.users signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, display_name, preferred_language)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', NULL),
        'en'
    )
    ON CONFLICT (id) DO NOTHING;

    INSERT INTO public.user_preferences (
        user_id,
        default_ranking_criterion,
        preferred_language,
        max_walking_distance_meters,
        wheelchair_accessible
    )
    VALUES (
        NEW.id,
        'fastest',
        'en',
        800.0,
        false
    )
    ON CONFLICT (user_id) DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Trigger for Recent Searches 20-item retention policy
CREATE OR REPLACE FUNCTION public.prune_recent_searches()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM public.recent_searches
    WHERE id IN (
        SELECT id FROM public.recent_searches
        WHERE user_id = NEW.user_id
        ORDER BY searched_at DESC
        OFFSET 20
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_recent_searches_retention ON public.recent_searches;
CREATE TRIGGER enforce_recent_searches_retention
    AFTER INSERT ON public.recent_searches
    FOR EACH ROW EXECUTE FUNCTION public.prune_recent_searches();

-- ==============================================================================
-- Row Level Security (RLS) Policies
-- ==============================================================================

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_journeys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recent_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_feedback ENABLE ROW LEVEL SECURITY;

-- Profiles: users only access their own profile
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
    ON public.profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can delete own profile"
    ON public.profiles FOR DELETE
    USING (auth.uid() = id);

-- Preferences: users only access their own preferences
CREATE POLICY "Users can view own preferences"
    ON public.user_preferences FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own preferences"
    ON public.user_preferences FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own preferences"
    ON public.user_preferences FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own preferences"
    ON public.user_preferences FOR DELETE
    USING (auth.uid() = user_id);

-- Saved Journeys: users only access their own journeys
CREATE POLICY "Users can view own saved journeys"
    ON public.saved_journeys FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own saved journeys"
    ON public.saved_journeys FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own saved journeys"
    ON public.saved_journeys FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own saved journeys"
    ON public.saved_journeys FOR DELETE
    USING (auth.uid() = user_id);

-- Recent Searches: users only access and clear their own history
CREATE POLICY "Users can view own recent searches"
    ON public.recent_searches FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own recent searches"
    ON public.recent_searches FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can clear own recent searches"
    ON public.recent_searches FOR DELETE
    USING (auth.uid() = user_id);

-- Feedback: authenticated users or anonymous can insert; users can only read their own
CREATE POLICY "Users and guests can submit feedback"
    ON public.user_feedback FOR INSERT
    WITH CHECK (user_id IS NULL OR auth.uid() = user_id);

CREATE POLICY "Users can view own feedback"
    ON public.user_feedback FOR SELECT
    USING (auth.uid() = user_id);

