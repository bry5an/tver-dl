create table series (
    id uuid primary key default gen_random_uuid(),

    -- TVer data
    tver_series_id text unique not null,
    name text not null,
    url text not null,

    -- config-like fields
    enabled boolean default true,

    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
