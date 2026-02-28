-- ClipSeek Multi-User Schema
-- Run in Supabase SQL Editor after enabling pgvector

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Profiles (extends Supabase auth.users)
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    avatar_url TEXT,
    api_key_enc TEXT,
    free_searches_today INT NOT NULL DEFAULT 0,
    free_indexes_this_month INT NOT NULL DEFAULT 0,
    last_search_reset DATE NOT NULL DEFAULT CURRENT_DATE,
    last_index_reset DATE NOT NULL DEFAULT (DATE_TRUNC('month', CURRENT_DATE))::DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO profiles (id, display_name, avatar_url)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', 'User'),
        COALESCE(NEW.raw_user_meta_data->>'avatar_url', NEW.raw_user_meta_data->>'picture', '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Channels
CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    youtube_handle TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT 'Unknown Channel',
    total_videos INT NOT NULL DEFAULT 0,
    indexed_at TIMESTAMPTZ,
    indexed_by UUID REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- User-channel subscriptions (shared-on-demand join table)
CREATE TABLE user_channels (
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, channel_id)
);

-- Videos
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    youtube_video_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL DEFAULT 'Unknown Title',
    thumbnail_url TEXT NOT NULL DEFAULT '',
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Transcript chunks with vector embeddings
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    start_seconds INT NOT NULL,
    end_seconds INT NOT NULL,
    embedding VECTOR(768) NOT NULL
);

-- Index for vector similarity search (HNSW works on empty tables, unlike ivfflat)
CREATE INDEX chunks_embedding_idx ON chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Index for filtering by video
CREATE INDEX chunks_video_id_idx ON chunks(video_id);

-- Index for video lookup by youtube ID
CREATE INDEX videos_youtube_id_idx ON videos(youtube_video_id);

-- Usage logs
CREATE TABLE usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('search', 'index')),
    video_count INT,
    used_own_key BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX usage_logs_user_date_idx ON usage_logs(user_id, created_at);

-- Search history
CREATE TABLE search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    result_chunk_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX search_history_user_idx ON search_history(user_id, created_at DESC);

-- Row-Level Security Policies
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_history ENABLE ROW LEVEL SECURITY;

-- Profiles: users can read/update their own profile
CREATE POLICY profiles_select ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY profiles_update ON profiles FOR UPDATE USING (auth.uid() = id);

-- Channels: anyone authenticated can read, insert handled by backend service role
CREATE POLICY channels_select ON channels FOR SELECT TO authenticated USING (true);

-- User_channels: users see their own subscriptions
CREATE POLICY user_channels_select ON user_channels FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY user_channels_insert ON user_channels FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY user_channels_delete ON user_channels FOR DELETE USING (auth.uid() = user_id);

-- Videos: anyone authenticated can read (shared data)
CREATE POLICY videos_select ON videos FOR SELECT TO authenticated USING (true);

-- Chunks: anyone authenticated can read (shared data, search scoping done in query)
CREATE POLICY chunks_select ON chunks FOR SELECT TO authenticated USING (true);

-- Usage logs: users see their own
CREATE POLICY usage_logs_select ON usage_logs FOR SELECT USING (auth.uid() = user_id);

-- Search history: users see their own
CREATE POLICY search_history_select ON search_history FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY search_history_insert ON search_history FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY search_history_delete ON search_history FOR DELETE USING (auth.uid() = user_id);
