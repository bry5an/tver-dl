create table subtitles (
    id uuid primary key default gen_random_uuid(),

    episode_id uuid not null references episodes(id) on delete cascade,

    -- availability state
    status text not null check (
        status in (
            'not_available',    -- not published yet
            'available',        -- published, not downloaded
            'downloaded',       -- successfully downloaded
            'missing',          -- expected but not found
            'failed'            -- download attempted but failed
        )
    ),

    -- files
    subtitle_format text,        -- srt, vtt, ass
    file_path text,

    -- timing
    checked_at timestamptz default now(),
    downloaded_at timestamptz,

    -- diagnostics
    error_message text,

    unique (episode_id)
);
