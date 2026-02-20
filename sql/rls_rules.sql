-- Row Level Security (RLS) for TVer Downloader Application
-- This application is single-user, so RLS is configured to allow authenticated users
-- to access all rows while preventing public anonymous access.

-- ============================================================================
-- ENABLE RLS ON TABLES
-- ============================================================================

ALTER TABLE downloads ENABLE ROW LEVEL SECURITY;

ALTER TABLE series ENABLE ROW LEVEL SECURITY;

ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- SERIES TABLE RLS
-- ============================================================================

-- Policy: Allow authenticated users to view all series
CREATE POLICY "Enable read access for authenticated users on series"
ON series
FOR SELECT
USING (auth.role() = 'authenticated_user');

-- Policy: Allow authenticated users to insert new series
CREATE POLICY "Enable insert access for authenticated users on series"
ON series
FOR INSERT
WITH CHECK (auth.role() = 'authenticated_user');

-- Policy: Allow authenticated users to update series
CREATE POLICY "Enable update access for authenticated users on series"
ON series
FOR UPDATE
USING (auth.role() = 'authenticated_user')
WITH CHECK (auth.role() = 'authenticated_user');

-- Policy: Allow authenticated users to delete series
CREATE POLICY "Enable delete access for authenticated users on series"
ON series
FOR DELETE
USING (auth.role() = 'authenticated_user');

-- ============================================================================
-- EPISODES TABLE RLS
-- ============================================================================

-- Policy: Allow authenticated users to view all episodes
CREATE POLICY "Enable read access for authenticated users on episodes"
ON episodes
FOR SELECT
USING (auth.role() = 'authenticated_user');

-- Policy: Allow authenticated users to insert new episodes
CREATE POLICY "Enable insert access for authenticated users on episodes"
ON episodes
FOR INSERT
WITH CHECK (auth.role() = 'authenticated_user');

-- Policy: Allow authenticated users to update episodes
CREATE POLICY "Enable update access for authenticated users on episodes"
ON episodes
FOR UPDATE
USING (auth.role() = 'authenticated_user')
WITH CHECK (auth.role() = 'authenticated_user');

-- Policy: Allow authenticated users to delete episodes
CREATE POLICY "Enable delete access for authenticated users on episodes"
ON episodes
FOR DELETE
USING (auth.role() = 'authenticated_user');

-- ============================================================================
-- DOWNLOADS TABLE RLS
-- ============================================================================

-- Policy: Allow authenticated users to view all downloads
CREATE POLICY "Enable read access for authenticated users on downloads"
ON downloads
FOR SELECT
USING (auth.role() = 'authenticated_user');

-- Policy: Allow authenticated users to insert new download records
CREATE POLICY "Enable insert access for authenticated users on downloads"
ON downloads
FOR INSERT
WITH CHECK (auth.role() = 'authenticated_user');

-- Policy: Allow authenticated users to update download records (e.g., status, completion)
CREATE POLICY "Enable update access for authenticated users on downloads"
ON downloads
FOR UPDATE
USING (auth.role() = 'authenticated_user')
WITH CHECK (auth.role() = 'authenticated_user');

-- Policy: Allow authenticated users to delete download records
CREATE POLICY "Enable delete access for authenticated users on downloads"
ON downloads
FOR DELETE
USING (auth.role() = 'authenticated_user');
