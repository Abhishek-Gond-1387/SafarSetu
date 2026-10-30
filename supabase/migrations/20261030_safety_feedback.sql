-- ══════════════════════════════════════════════════════════════════════════
-- SAFARSETU: HerRoute - Women's Safety Community Feedback Migration
-- ══════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Main Safety Feedback Table
CREATE TABLE IF NOT EXISTS public.safety_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    journey_id VARCHAR(255) NULL,
    route_id VARCHAR(255) NULL,
    segment_id VARCHAR(255) NOT NULL,
    segment_type VARCHAR(50) NOT NULL DEFAULT 'entire_journey',
    segment_name VARCHAR(255) NULL,
    experience_rating VARCHAR(30) NOT NULL CHECK (experience_rating IN ('comfortable', 'uncomfortable', 'unsafe')),
    safety_concerns TEXT[] NOT NULL DEFAULT '{}',
    feedback_text TEXT NULL,
    time_category VARCHAR(20) NOT NULL DEFAULT 'daytime' CHECK (time_category IN ('daytime', 'nighttime')),
    moderation_status VARCHAR(20) NOT NULL DEFAULT 'approved' CHECK (moderation_status IN ('pending', 'approved', 'flagged', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. Indexes for Fast Segment & Route Aggregations
CREATE INDEX IF NOT EXISTS idx_safety_feedback_segment_status ON public.safety_feedback (segment_id, moderation_status);
CREATE INDEX IF NOT EXISTS idx_safety_feedback_route_status ON public.safety_feedback (route_id, moderation_status);
CREATE INDEX IF NOT EXISTS idx_safety_feedback_time ON public.safety_feedback (time_category);
CREATE INDEX IF NOT EXISTS idx_safety_feedback_user ON public.safety_feedback (user_id);
CREATE INDEX IF NOT EXISTS idx_safety_feedback_created ON public.safety_feedback (created_at DESC);

-- 3. Prevent Duplicate Feedback for same User, Journey & Segment
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_user_journey_segment 
ON public.safety_feedback (user_id, COALESCE(journey_id, 'standalone'), segment_id);

-- 4. Row Level Security (RLS) Policies
ALTER TABLE public.safety_feedback ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own submissions
CREATE POLICY "Users can read own safety feedback"
    ON public.safety_feedback
    FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Authenticated users can insert their own feedback
CREATE POLICY "Authenticated users can submit safety feedback"
    ON public.safety_feedback
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update or delete their own feedback
CREATE POLICY "Users can update own safety feedback"
    ON public.safety_feedback
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own safety feedback"
    ON public.safety_feedback
    FOR DELETE
    USING (auth.uid() = user_id);

-- 5. Aggregated View for Public/Commuter Access (Zero Personal Data Leaked)
CREATE OR REPLACE VIEW public.route_safety_aggregated_summary AS
SELECT 
    segment_id,
    route_id,
    time_category,
    COUNT(*) AS total_reports,
    COUNT(*) FILTER (WHERE experience_rating = 'comfortable') AS comfortable_count,
    COUNT(*) FILTER (WHERE experience_rating = 'uncomfortable') AS uncomfortable_count,
    COUNT(*) FILTER (WHERE experience_rating = 'unsafe') AS unsafe_count
FROM public.safety_feedback
WHERE moderation_status = 'approved'
GROUP BY segment_id, route_id, time_category;

-- Grant select on view to public & authenticated users
GRANT SELECT ON public.route_safety_aggregated_summary TO anon, authenticated;
