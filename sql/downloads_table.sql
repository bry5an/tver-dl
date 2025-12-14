create table downloads (
    id uuid primary key default gen_random_uuid(),

    episode_id uuid not null references episodes(id) on delete cascade,

    -- download lifecycle
    status text not null check (status in ('pending', 'downloaded', 'failed', 'skipped')),
    downloaded_at timestamptz,

    -- file output
    file_path text,
    file_size_bytes bigint,

    -- diagnostics
    error_message text,
    downloader_host text, -- "macbook", "homeserver", etc.

    created_at timestamptz default now(),

    -- prevent duplicate successful downloads
    unique (episode_id)
);
