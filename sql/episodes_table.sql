create table episodes (
    id uuid primary key default gen_random_uuid(),

    series_id uuid not null references series(id) on delete cascade,

    -- TVer identifiers
    tver_episode_id text unique not null,
    title text not null,
    episode_number integer,

    -- URLs & timing
    episode_url text not null,
    published_at timestamptz,

    created_at timestamptz default now()
);
