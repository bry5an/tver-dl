alter table series
add column has_subtitles boolean;

alter table episodes
add column subtitles_published_at timestamptz;

alter table episodes
add column subtitles_checked_at timestamptz;

alter table subtitles
add column series_name text;

alter table subtitles
add column episode_title text;