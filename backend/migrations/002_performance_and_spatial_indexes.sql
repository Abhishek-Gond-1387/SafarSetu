-- ==============================================================================
-- SafarSetu — Stage 5: High-Performance Database Indexing & Query Optimization
-- Description: Adds B-Tree, composite, and partial indexes to optimize
--              HerRoute community safety insights, saved journeys, and user queries.
-- Target: Supabase / PostgreSQL 15+
-- ==============================================================================

-- 1. HerRoute Community Safety Insights Lookups (Crucial for Route Comparison Cards)
-- Accelerates route card aggregate queries: WHERE route_id = $1 AND moderation_status = 'published'
CREATE INDEX IF NOT EXISTS idx_safety_feedback_route_moderated 
ON public.safety_feedback (route_id, moderation_status);

-- 2. HerRoute Daytime vs Nighttime Time-Slice Index
-- Accelerates time-filtered queries: WHERE route_id = $1 AND journey_time_category = $2
CREATE INDEX IF NOT EXISTS idx_safety_feedback_time_filter 
ON public.safety_feedback (route_id, journey_time_category, moderation_status);

-- 3. Segment-Level Safety Aggregate Index
-- Accelerates station/interchange/segment feedback lookups
CREATE INDEX IF NOT EXISTS idx_safety_feedback_segment 
ON public.safety_feedback (segment_id, moderation_status)
WHERE segment_id IS NOT NULL;

-- 4. User Personal History & Duplicate Feedback Check Index
-- Accelerates user dashboard queries and prevents duplicate submissions
CREATE INDEX IF NOT EXISTS idx_safety_feedback_user_history 
ON public.safety_feedback (user_id, created_at DESC);

-- 5. Saved Journeys Route Lookup Index
-- Accelerates finding common origin-destination corridors across commuters
CREATE INDEX IF NOT EXISTS idx_saved_journeys_corridor 
ON public.saved_journeys (origin_stop_id, destination_stop_id);

-- 6. User Profiles Fast Lookup
CREATE INDEX IF NOT EXISTS idx_profiles_updated_at 
ON public.profiles (updated_at DESC);

-- 7. Analyze Tables to refresh planner statistics
ANALYZE public.safety_feedback;
ANALYZE public.saved_journeys;
ANALYZE public.profiles;

