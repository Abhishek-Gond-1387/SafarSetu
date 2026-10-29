# SafarSetu — Stage 4: Supabase Database & Auth Setup Guide

This guide details how to set up the persistent user layer for **SafarSetu** using Supabase PostgreSQL and Supabase Auth with Row Level Security (RLS).

---

## 1. Creating the Supabase Project

1. Log in to your account at [https://supabase.com](https://supabase.com) and click **New Project**.
2. Set the project details:
   - **Name:** `SafarSetu`
   - **Database Password:** Generate and store securely.
   - **Region:** Select `ap-south-1` (Mumbai / India) for lowest latency to Delhi/NCR users.
3. Once the database finishes provisioning (~2 minutes), navigate to:
   - **Project Settings → API**: Copy the `Project URL`, `anon / public key`, and `service_role key`.
   - **Project Settings → API → JWT Settings**: Copy the `JWT Secret`.

> [!CAUTION]
> **Credential Security:**
> Never paste the `service_role key` or database password into client-side code, git commits, or chat sessions.
> The `service_role key` bypasses all Row Level Security policies and must remain strictly on the backend.

---

## 2. Applying Database Migrations

You can apply the Stage 4 SQL migration through either the **Supabase Dashboard** or the **Supabase CLI**.

### Option A: Via Supabase Web Dashboard (Recommended for quick setup)
1. In the Supabase Dashboard, open **SQL Editor**.
2. Click **New Query**.
3. Copy and paste the entire contents of [`backend/migrations/001_stage4_user_database_auth.sql`](file:///d:/SafarSetu/backend/migrations/001_stage4_user_database_auth.sql).
4. Click **Run**.
5. Check the **Table Editor** to confirm the creation of:
   - `profiles`
   - `user_preferences`
   - `saved_journeys`
   - `recent_searches`
   - `user_feedback`

### Option B: Via Supabase CLI
```bash
# Link your local repository to your Supabase project
npx supabase link --project-ref your-project-ref

# Push the migration
npx supabase db push
```

---

## 3. Configuring Authentication & Redirect URLs

1. In the Supabase Dashboard, navigate to **Authentication → URL Configuration**.
2. Configure:
   - **Site URL:** `http://localhost:3000` (or `http://localhost:5173` for Vite).
   - **Redirect URLs:** Add:
     - `http://localhost:3000/**`
     - `http://localhost:5173/**`
     - `http://127.0.0.1:3000/**`
     - `http://127.0.0.1:5173/**`
3. Under **Authentication → Providers → Email**:
   - Ensure **Enable Email provider** is enabled.
   - For local development, you may disable **Confirm email** to allow immediate testing without an SMTP server.

---

## 4. Environment Variables Configuration

### Backend Configuration (`backend/.env`)
Copy `backend/.env.example` to `backend/.env` and update the Supabase section:

```ini
# Supabase Configuration
SUPABASE_URL="https://your-project-id.supabase.co"
SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
SUPABASE_JWT_SECRET="your-supabase-jwt-secret-from-dashboard"
SUPABASE_JWT_ALGORITHM="HS256"
SUPABASE_JWT_AUDIENCE="authenticated"
```

### Frontend Configuration (`frontend/.env`)
```ini
# For Vite
VITE_SUPABASE_URL="https://your-project-id.supabase.co"
VITE_SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
VITE_API_BASE_URL="http://localhost:8000/api/v1"

# For Next.js
NEXT_PUBLIC_SUPABASE_URL="https://your-project-id.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000/api/v1"
```

---

## 5. Running the Application Locally

1. Start the FastAPI backend:
   ```bash
   cd backend
   python run.py
   ```
2. The server initializes at `http://localhost:8000`. Interactive documentation is available at `http://localhost:8000/docs`.

---

## 6. Testing Row Level Security (RLS) with Two User Accounts

To empirically test RLS isolation between distinct users:

### Step 1: Create Two Test Users in Supabase
In Supabase Dashboard under **Authentication → Users → Add User**:
- **User A:** `commuter_a@example.com` / `Password123!`
- **User B:** `commuter_b@example.com` / `Password123!`

### Step 2: Obtain User Tokens via cURL or Frontend Client
```bash
# Obtain User A Access Token
curl -X POST 'https://your-project.supabase.co/auth/v1/token?grant_type=password' \
  -H "apikey: your-anon-key" \
  -H "Content-Type: application/json" \
  -d '{"email": "commuter_a@example.com", "password": "Password123!"}'

# Obtain User B Access Token
curl -X POST 'https://your-project.supabase.co/auth/v1/token?grant_type=password' \
  -H "apikey: your-anon-key" \
  -H "Content-Type: application/json" \
  -d '{"email": "commuter_b@example.com", "password": "Password123!"}'
```

### Step 3: Test Isolation on Saved Journeys
1. **User A saves a journey:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/users/me/saved-journeys \
     -H "Authorization: Bearer <USER_A_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"journey_name": "Work Route", "origin_stop_id": "3127", "destination_stop_id": "2024"}'
   ```
   *Record the returned `id` (e.g., `JOURNEY_ID_A`).*

2. **User B queries saved journeys:**
   ```bash
   curl -X GET http://localhost:8000/api/v1/users/me/saved-journeys \
     -H "Authorization: Bearer <USER_B_TOKEN>"
   ```
   *Result:* Returns `{"total": 0, "results": []}`. User B cannot see User A's saved journey.

3. **User B attempts to delete User A's journey:**
   ```bash
   curl -X DELETE http://localhost:8000/api/v1/users/me/saved-journeys/<JOURNEY_ID_A> \
     -H "Authorization: Bearer <USER_B_TOKEN>"
   ```
   *Result:* Returns `HTTP 404 Not Found` (`"Saved journey not found or not owned by current user"`). User B cannot modify User A's data.

---

## 7. Automated Test Suite

Run the full automated test suite containing both transit routing tests and authentication tests:

```bash
python -m pytest backend/tests/ -v
```

All 66 tests pass out of the box using isolated deterministic fixtures with strict RLS simulation.

