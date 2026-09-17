-- =============================================================================
-- CareerMatch AI — Supabase Migration
-- Run this ONCE in: Supabase Dashboard → SQL Editor → New Query → Run
--
-- What this does:
--   1. Creates the public.profiles table
--   2. Adds foreign key to auth.users
--   3. Enables Row Level Security (RLS)
--   4. Adds SELECT / INSERT / UPDATE policies (user sees only their own row)
--   5. Adds a trigger to auto-create a profile when a new user signs up
-- =============================================================================


-- ── 1. Create profiles table ─────────────────────────────────────────────────
create table if not exists public.profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    full_name   text,
    email       text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

comment on table public.profiles is
    'One row per authenticated user. Stores display name and email for CareerMatch AI.';


-- ── 2. Enable Row Level Security ─────────────────────────────────────────────
alter table public.profiles enable row level security;


-- ── 3. RLS Policies ──────────────────────────────────────────────────────────

-- Users can read their OWN profile only
create policy "Users can view own profile"
    on public.profiles
    for select
    using (auth.uid() = id);

-- Users can insert their OWN profile only (enforced at registration)
create policy "Users can insert own profile"
    on public.profiles
    for insert
    with check (auth.uid() = id);

-- Users can update their OWN profile only
create policy "Users can update own profile"
    on public.profiles
    for update
    using (auth.uid() = id);


-- ── 4. updated_at trigger function ───────────────────────────────────────────
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create or replace trigger profiles_updated_at
    before update on public.profiles
    for each row
    execute procedure public.set_updated_at();


-- ── 5. Auto-create profile row when a new auth user registers ────────────────
--
-- This trigger fires whenever a row is inserted into auth.users (i.e., when
-- someone signs up). It reads full_name from the user metadata passed during
-- sign-up, and copies the email from auth.users.
--
-- security definer: runs with the privileges of the function owner (postgres),
-- so it can insert into profiles even before the user's RLS context is active.

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, full_name, email)
    values (
        new.id,
        coalesce(new.raw_user_meta_data ->> 'full_name', ''),
        new.email
    )
    on conflict (id) do nothing;   -- safe to re-run; won't overwrite existing rows
    return new;
end;
$$;

-- Drop the trigger first so re-running the script is idempotent
drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
    after insert on auth.users
    for each row
    execute procedure public.handle_new_user();


-- ── 6. Future user-specific tables: reference pattern ────────────────────────
--
-- When adding future CareerMatch AI data tables, use this pattern:
--
--   create table public.resume_sessions (
--       id          uuid primary key default gen_random_uuid(),
--       user_id     uuid not null references auth.users(id) on delete cascade,
--       ...
--   );
--   alter table public.resume_sessions enable row level security;
--   create policy "own data only" on public.resume_sessions
--       for all using (auth.uid() = user_id);
--
-- DO NOT create these tables now — only profiles is needed for authentication.


-- ── Verification query (run after migration to confirm everything is set up) ─
-- select
--     tablename,
--     rowsecurity
-- from pg_tables
-- where schemaname = 'public' and tablename = 'profiles';
