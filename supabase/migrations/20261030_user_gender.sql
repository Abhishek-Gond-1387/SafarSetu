-- ==============================================================================
-- SafarSetu — Migration: Add Gender to Profiles Table
-- Description: Adds gender column with CHECK constraint and updates the 
--              auth.users trigger to persist gender from user_metadata.
-- ==============================================================================

-- 1. Add gender column to public.profiles
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS gender TEXT NULL 
CHECK (gender IS NULL OR gender IN ('male', 'female', 'other', 'prefer_not_to_say'));

COMMENT ON COLUMN public.profiles.gender IS 'Optional commuter gender self-identification: male, female, other, prefer_not_to_say';

-- 2. Update trigger function to record gender on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, display_name, preferred_language, gender)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', NULL),
        'en',
        NEW.raw_user_meta_data->>'gender'
    )
    ON CONFLICT (id) DO UPDATE SET
        gender = COALESCE(EXCLUDED.gender, public.profiles.gender),
        display_name = COALESCE(EXCLUDED.display_name, public.profiles.display_name);

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

