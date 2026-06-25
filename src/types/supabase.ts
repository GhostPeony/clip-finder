export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: '14.5';
  };
  graphql_public: {
    Tables: {
      [_ in never]: never;
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      graphql: {
        Args: {
          extensions?: Json;
          operationName?: string;
          query?: string;
          variables?: Json;
        };
        Returns: Json;
      };
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
  public: {
    Tables: {
      agent_notes: {
        Row: {
          content: string;
          created_at: string;
          created_by: string;
          created_by_client: string | null;
          id: string;
          metadata: Json;
          source_refs: Json;
          tags: string[];
          updated_at: string;
          user_id: string;
        };
        Insert: {
          content: string;
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          id?: string;
          metadata?: Json;
          source_refs?: Json;
          tags?: string[];
          updated_at?: string;
          user_id: string;
        };
        Update: {
          content?: string;
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          id?: string;
          metadata?: Json;
          source_refs?: Json;
          tags?: string[];
          updated_at?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'agent_notes_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      channels: {
        Row: {
          created_at: string;
          id: string;
          indexed_at: string | null;
          indexed_by: string | null;
          name: string;
          total_videos: number;
          youtube_handle: string;
        };
        Insert: {
          created_at?: string;
          id?: string;
          indexed_at?: string | null;
          indexed_by?: string | null;
          name?: string;
          total_videos?: number;
          youtube_handle: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          indexed_at?: string | null;
          indexed_by?: string | null;
          name?: string;
          total_videos?: number;
          youtube_handle?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'channels_indexed_by_fkey';
            columns: ['indexed_by'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      chunks: {
        Row: {
          content: string;
          embedding: string;
          end_seconds: number;
          id: string;
          start_seconds: number;
          video_id: string;
        };
        Insert: {
          content: string;
          embedding: string;
          end_seconds: number;
          id?: string;
          start_seconds: number;
          video_id: string;
        };
        Update: {
          content?: string;
          embedding?: string;
          end_seconds?: number;
          id?: string;
          start_seconds?: number;
          video_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'chunks_video_id_fkey';
            columns: ['video_id'];
            isOneToOne: false;
            referencedRelation: 'videos';
            referencedColumns: ['id'];
          },
        ];
      };
      context_preferences: {
        Row: {
          created_at: string;
          created_by: string;
          created_by_client: string | null;
          id: string;
          metadata: Json;
          reason: string;
          relevance: string;
          source_ref: Json;
          updated_at: string;
          user_id: string;
        };
        Insert: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          id?: string;
          metadata?: Json;
          reason?: string;
          relevance: string;
          source_ref: Json;
          updated_at?: string;
          user_id: string;
        };
        Update: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          id?: string;
          metadata?: Json;
          reason?: string;
          relevance?: string;
          source_ref?: Json;
          updated_at?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'context_preferences_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      ingestion_job_events: {
        Row: {
          created_at: string;
          id: string;
          job_id: string;
          level: string;
          message: string;
          reason: string | null;
          youtube_video_id: string | null;
        };
        Insert: {
          created_at?: string;
          id?: string;
          job_id: string;
          level?: string;
          message: string;
          reason?: string | null;
          youtube_video_id?: string | null;
        };
        Update: {
          created_at?: string;
          id?: string;
          job_id?: string;
          level?: string;
          message?: string;
          reason?: string | null;
          youtube_video_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: 'ingestion_job_events_job_id_fkey';
            columns: ['job_id'];
            isOneToOne: false;
            referencedRelation: 'ingestion_jobs';
            referencedColumns: ['id'];
          },
        ];
      };
      ingestion_jobs: {
        Row: {
          completed_at: string | null;
          cost_estimate: Json;
          created_at: string;
          error: string | null;
          failed_video_count: number;
          id: string;
          indexed_video_count: number;
          last_message: string | null;
          requested_video_count: number;
          skipped_video_count: number;
          source_type: string;
          source_url: string;
          started_at: string | null;
          status: string;
          updated_at: string;
          user_id: string;
        };
        Insert: {
          completed_at?: string | null;
          cost_estimate?: Json;
          created_at?: string;
          error?: string | null;
          failed_video_count?: number;
          id?: string;
          indexed_video_count?: number;
          last_message?: string | null;
          requested_video_count?: number;
          skipped_video_count?: number;
          source_type?: string;
          source_url: string;
          started_at?: string | null;
          status?: string;
          updated_at?: string;
          user_id: string;
        };
        Update: {
          completed_at?: string | null;
          cost_estimate?: Json;
          created_at?: string;
          error?: string | null;
          failed_video_count?: number;
          id?: string;
          indexed_video_count?: number;
          last_message?: string | null;
          requested_video_count?: number;
          skipped_video_count?: number;
          source_type?: string;
          source_url?: string;
          started_at?: string | null;
          status?: string;
          updated_at?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'ingestion_jobs_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      knowledge_artifacts: {
        Row: {
          artifact_type: string;
          content: string;
          created_at: string;
          created_by: string;
          id: string;
          metadata: Json;
          source_refs: Json;
          summary: string;
          title: string;
          updated_at: string;
          user_id: string | null;
          video_id: string | null;
        };
        Insert: {
          artifact_type: string;
          content?: string;
          created_at?: string;
          created_by?: string;
          id?: string;
          metadata?: Json;
          source_refs?: Json;
          summary?: string;
          title: string;
          updated_at?: string;
          user_id?: string | null;
          video_id?: string | null;
        };
        Update: {
          artifact_type?: string;
          content?: string;
          created_at?: string;
          created_by?: string;
          id?: string;
          metadata?: Json;
          source_refs?: Json;
          summary?: string;
          title?: string;
          updated_at?: string;
          user_id?: string | null;
          video_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: 'knowledge_artifacts_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'knowledge_artifacts_video_id_fkey';
            columns: ['video_id'];
            isOneToOne: false;
            referencedRelation: 'videos';
            referencedColumns: ['id'];
          },
        ];
      };
      mcp_tokens: {
        Row: {
          created_at: string;
          expires_at: string | null;
          id: string;
          last_used_at: string | null;
          name: string;
          revoked_at: string | null;
          scopes: string[];
          token_hash: string;
          token_prefix: string;
          user_id: string;
        };
        Insert: {
          created_at?: string;
          expires_at?: string | null;
          id?: string;
          last_used_at?: string | null;
          name?: string;
          revoked_at?: string | null;
          scopes?: string[];
          token_hash: string;
          token_prefix: string;
          user_id: string;
        };
        Update: {
          created_at?: string;
          expires_at?: string | null;
          id?: string;
          last_used_at?: string | null;
          name?: string;
          revoked_at?: string | null;
          scopes?: string[];
          token_hash?: string;
          token_prefix?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'mcp_tokens_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      personal_concepts: {
        Row: {
          created_at: string;
          created_by: string;
          created_by_client: string | null;
          id: string;
          metadata: Json;
          name: string;
          source_refs: Json;
          status: string;
          summary: string;
          updated_at: string;
          user_id: string;
        };
        Insert: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          id?: string;
          metadata?: Json;
          name: string;
          source_refs?: Json;
          status?: string;
          summary?: string;
          updated_at?: string;
          user_id: string;
        };
        Update: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          id?: string;
          metadata?: Json;
          name?: string;
          source_refs?: Json;
          status?: string;
          summary?: string;
          updated_at?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'personal_concepts_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      personal_context_links: {
        Row: {
          created_at: string;
          created_by: string;
          created_by_client: string | null;
          from_ref: Json;
          id: string;
          metadata: Json;
          note: string;
          relation: string;
          to_ref: Json;
          user_id: string;
        };
        Insert: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          from_ref: Json;
          id?: string;
          metadata?: Json;
          note?: string;
          relation?: string;
          to_ref: Json;
          user_id: string;
        };
        Update: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          from_ref?: Json;
          id?: string;
          metadata?: Json;
          note?: string;
          relation?: string;
          to_ref?: Json;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'personal_context_links_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      profiles: {
        Row: {
          api_key_enc: string | null;
          avatar_url: string | null;
          created_at: string;
          display_name: string | null;
          free_indexed_seconds_total: number;
          free_indexed_videos_total: number;
          free_indexes_this_month: number;
          free_searches_this_month: number;
          free_searches_today: number;
          id: string;
          last_index_reset: string;
          last_search_month_reset: string;
          last_search_reset: string;
          onboarding_completed_at: string | null;
          onboarding_skipped_at: string | null;
          onboarding_state: Json;
          onboarding_step: string;
        };
        Insert: {
          api_key_enc?: string | null;
          avatar_url?: string | null;
          created_at?: string;
          display_name?: string | null;
          free_indexed_seconds_total?: number;
          free_indexed_videos_total?: number;
          free_indexes_this_month?: number;
          free_searches_this_month?: number;
          free_searches_today?: number;
          id: string;
          last_index_reset?: string;
          last_search_month_reset?: string;
          last_search_reset?: string;
          onboarding_completed_at?: string | null;
          onboarding_skipped_at?: string | null;
          onboarding_state?: Json;
          onboarding_step?: string;
        };
        Update: {
          api_key_enc?: string | null;
          avatar_url?: string | null;
          created_at?: string;
          display_name?: string | null;
          free_indexed_seconds_total?: number;
          free_indexed_videos_total?: number;
          free_indexes_this_month?: number;
          free_searches_this_month?: number;
          free_searches_today?: number;
          id?: string;
          last_index_reset?: string;
          last_search_month_reset?: string;
          last_search_reset?: string;
          onboarding_completed_at?: string | null;
          onboarding_skipped_at?: string | null;
          onboarding_state?: Json;
          onboarding_step?: string;
        };
        Relationships: [];
      };
      search_history: {
        Row: {
          created_at: string;
          id: string;
          query: string;
          result_chunk_ids: string[] | null;
          user_id: string;
        };
        Insert: {
          created_at?: string;
          id?: string;
          query: string;
          result_chunk_ids?: string[] | null;
          user_id: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          query?: string;
          result_chunk_ids?: string[] | null;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'search_history_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      source_concepts: {
        Row: {
          concept_type: string;
          created_at: string;
          id: string;
          metadata: Json;
          name: string;
          source_refs: Json;
          summary: string;
          updated_at: string;
          video_id: string | null;
        };
        Insert: {
          concept_type?: string;
          created_at?: string;
          id?: string;
          metadata?: Json;
          name: string;
          source_refs?: Json;
          summary?: string;
          updated_at?: string;
          video_id?: string | null;
        };
        Update: {
          concept_type?: string;
          created_at?: string;
          id?: string;
          metadata?: Json;
          name?: string;
          source_refs?: Json;
          summary?: string;
          updated_at?: string;
          video_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: 'source_concepts_video_id_fkey';
            columns: ['video_id'];
            isOneToOne: false;
            referencedRelation: 'videos';
            referencedColumns: ['id'];
          },
        ];
      };
      source_edges: {
        Row: {
          created_at: string;
          evidence_refs: Json;
          from_ref: Json;
          id: string;
          metadata: Json;
          relation: string;
          to_ref: Json;
          video_id: string | null;
        };
        Insert: {
          created_at?: string;
          evidence_refs?: Json;
          from_ref: Json;
          id?: string;
          metadata?: Json;
          relation: string;
          to_ref: Json;
          video_id?: string | null;
        };
        Update: {
          created_at?: string;
          evidence_refs?: Json;
          from_ref?: Json;
          id?: string;
          metadata?: Json;
          relation?: string;
          to_ref?: Json;
          video_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: 'source_edges_video_id_fkey';
            columns: ['video_id'];
            isOneToOne: false;
            referencedRelation: 'videos';
            referencedColumns: ['id'];
          },
        ];
      };
      source_labels: {
        Row: {
          confidence: number | null;
          created_at: string;
          id: string;
          label: string;
          label_type: string;
          metadata: Json;
          source_refs: Json;
          updated_at: string;
          video_id: string;
        };
        Insert: {
          confidence?: number | null;
          created_at?: string;
          id?: string;
          label: string;
          label_type: string;
          metadata?: Json;
          source_refs?: Json;
          updated_at?: string;
          video_id: string;
        };
        Update: {
          confidence?: number | null;
          created_at?: string;
          id?: string;
          label?: string;
          label_type?: string;
          metadata?: Json;
          source_refs?: Json;
          updated_at?: string;
          video_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'source_labels_video_id_fkey';
            columns: ['video_id'];
            isOneToOne: false;
            referencedRelation: 'videos';
            referencedColumns: ['id'];
          },
        ];
      };
      transcript_lines: {
        Row: {
          content: string;
          created_at: string;
          end_seconds: number;
          id: string;
          language: string | null;
          metadata: Json;
          source: string;
          start_seconds: number;
          video_id: string;
        };
        Insert: {
          content: string;
          created_at?: string;
          end_seconds: number;
          id?: string;
          language?: string | null;
          metadata?: Json;
          source?: string;
          start_seconds: number;
          video_id: string;
        };
        Update: {
          content?: string;
          created_at?: string;
          end_seconds?: number;
          id?: string;
          language?: string | null;
          metadata?: Json;
          source?: string;
          start_seconds?: number;
          video_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'transcript_lines_video_id_fkey';
            columns: ['video_id'];
            isOneToOne: false;
            referencedRelation: 'videos';
            referencedColumns: ['id'];
          },
        ];
      };
      usage_logs: {
        Row: {
          action: string;
          created_at: string;
          id: string;
          result_limit: number | null;
          transcript_seconds: number | null;
          used_own_key: boolean;
          user_id: string;
          video_count: number | null;
        };
        Insert: {
          action: string;
          created_at?: string;
          id?: string;
          result_limit?: number | null;
          transcript_seconds?: number | null;
          used_own_key?: boolean;
          user_id: string;
          video_count?: number | null;
        };
        Update: {
          action?: string;
          created_at?: string;
          id?: string;
          result_limit?: number | null;
          transcript_seconds?: number | null;
          used_own_key?: boolean;
          user_id?: string;
          video_count?: number | null;
        };
        Relationships: [
          {
            foreignKeyName: 'usage_logs_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      user_channels: {
        Row: {
          added_at: string;
          channel_id: string;
          user_id: string;
        };
        Insert: {
          added_at?: string;
          channel_id: string;
          user_id: string;
        };
        Update: {
          added_at?: string;
          channel_id?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'user_channels_channel_id_fkey';
            columns: ['channel_id'];
            isOneToOne: false;
            referencedRelation: 'channels';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'user_channels_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      user_videos: {
        Row: {
          access_source: string;
          added_at: string;
          source_url: string | null;
          user_id: string;
          video_id: string;
        };
        Insert: {
          access_source?: string;
          added_at?: string;
          source_url?: string | null;
          user_id: string;
          video_id: string;
        };
        Update: {
          access_source?: string;
          added_at?: string;
          source_url?: string | null;
          user_id?: string;
          video_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'user_videos_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'user_videos_video_id_fkey';
            columns: ['video_id'];
            isOneToOne: false;
            referencedRelation: 'videos';
            referencedColumns: ['id'];
          },
        ];
      };
      videos: {
        Row: {
          channel_id: string;
          id: string;
          indexed_at: string;
          thumbnail_url: string;
          title: string;
          transcript_seconds: number;
          youtube_video_id: string;
        };
        Insert: {
          channel_id: string;
          id?: string;
          indexed_at?: string;
          thumbnail_url?: string;
          title?: string;
          transcript_seconds?: number;
          youtube_video_id: string;
        };
        Update: {
          channel_id?: string;
          id?: string;
          indexed_at?: string;
          thumbnail_url?: string;
          title?: string;
          transcript_seconds?: number;
          youtube_video_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'videos_channel_id_fkey';
            columns: ['channel_id'];
            isOneToOne: false;
            referencedRelation: 'channels';
            referencedColumns: ['id'];
          },
        ];
      };
      workflow_artifacts: {
        Row: {
          artifact_type: string;
          created_at: string;
          id: string;
          metadata: Json;
          payload: Json;
          source_refs: Json;
          status: string;
          title: string;
          updated_at: string;
          workflow_instance_id: string;
        };
        Insert: {
          artifact_type: string;
          created_at?: string;
          id?: string;
          metadata?: Json;
          payload?: Json;
          source_refs?: Json;
          status?: string;
          title?: string;
          updated_at?: string;
          workflow_instance_id: string;
        };
        Update: {
          artifact_type?: string;
          created_at?: string;
          id?: string;
          metadata?: Json;
          payload?: Json;
          source_refs?: Json;
          status?: string;
          title?: string;
          updated_at?: string;
          workflow_instance_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'workflow_artifacts_workflow_instance_id_fkey';
            columns: ['workflow_instance_id'];
            isOneToOne: false;
            referencedRelation: 'workflow_instances';
            referencedColumns: ['id'];
          },
        ];
      };
      workflow_definitions: {
        Row: {
          created_at: string;
          created_by: string;
          created_by_client: string | null;
          description: string;
          id: string;
          key: string;
          metadata: Json;
          outputs: Json;
          policies: Json;
          status: string;
          steps: Json;
          title: string;
          trigger: string;
          updated_at: string;
          user_id: string | null;
          version: number;
        };
        Insert: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          description?: string;
          id?: string;
          key: string;
          metadata?: Json;
          outputs?: Json;
          policies?: Json;
          status?: string;
          steps?: Json;
          title?: string;
          trigger?: string;
          updated_at?: string;
          user_id?: string | null;
          version?: number;
        };
        Update: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          description?: string;
          id?: string;
          key?: string;
          metadata?: Json;
          outputs?: Json;
          policies?: Json;
          status?: string;
          steps?: Json;
          title?: string;
          trigger?: string;
          updated_at?: string;
          user_id?: string | null;
          version?: number;
        };
        Relationships: [
          {
            foreignKeyName: 'workflow_definitions_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      workflow_instances: {
        Row: {
          completed_at: string | null;
          cost_estimate: Json;
          created_at: string;
          created_by: string;
          created_by_client: string | null;
          current_step: string | null;
          error: string | null;
          id: string;
          input: Json;
          metadata: Json;
          result: Json;
          started_at: string | null;
          status: string;
          trigger: string;
          updated_at: string;
          user_id: string;
          workflow_definition_id: string | null;
          workflow_key: string;
          workflow_version: number;
        };
        Insert: {
          completed_at?: string | null;
          cost_estimate?: Json;
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          current_step?: string | null;
          error?: string | null;
          id?: string;
          input?: Json;
          metadata?: Json;
          result?: Json;
          started_at?: string | null;
          status?: string;
          trigger?: string;
          updated_at?: string;
          user_id: string;
          workflow_definition_id?: string | null;
          workflow_key: string;
          workflow_version?: number;
        };
        Update: {
          completed_at?: string | null;
          cost_estimate?: Json;
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          current_step?: string | null;
          error?: string | null;
          id?: string;
          input?: Json;
          metadata?: Json;
          result?: Json;
          started_at?: string | null;
          status?: string;
          trigger?: string;
          updated_at?: string;
          user_id?: string;
          workflow_definition_id?: string | null;
          workflow_key?: string;
          workflow_version?: number;
        };
        Relationships: [
          {
            foreignKeyName: 'workflow_instances_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'workflow_instances_workflow_definition_id_fkey';
            columns: ['workflow_definition_id'];
            isOneToOne: false;
            referencedRelation: 'workflow_definitions';
            referencedColumns: ['id'];
          },
        ];
      };
      workflow_steps: {
        Row: {
          attempt: number;
          completed_at: string | null;
          created_at: string;
          error: string | null;
          id: string;
          input_ref: Json;
          metrics: Json;
          output_ref: Json;
          started_at: string | null;
          status: string;
          step_key: string;
          workflow_instance_id: string;
        };
        Insert: {
          attempt?: number;
          completed_at?: string | null;
          created_at?: string;
          error?: string | null;
          id?: string;
          input_ref?: Json;
          metrics?: Json;
          output_ref?: Json;
          started_at?: string | null;
          status?: string;
          step_key: string;
          workflow_instance_id: string;
        };
        Update: {
          attempt?: number;
          completed_at?: string | null;
          created_at?: string;
          error?: string | null;
          id?: string;
          input_ref?: Json;
          metrics?: Json;
          output_ref?: Json;
          started_at?: string | null;
          status?: string;
          step_key?: string;
          workflow_instance_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'workflow_steps_workflow_instance_id_fkey';
            columns: ['workflow_instance_id'];
            isOneToOne: false;
            referencedRelation: 'workflow_instances';
            referencedColumns: ['id'];
          },
        ];
      };
      youtube_capture_items: {
        Row: {
          capture_source_id: string;
          discovered_at: string;
          id: string;
          ingestion_job_id: string | null;
          metadata: Json;
          playlist_item_id: string | null;
          skip_reason: string | null;
          source_added_at: string | null;
          status: string;
          updated_at: string;
          user_id: string;
          youtube_video_id: string;
        };
        Insert: {
          capture_source_id: string;
          discovered_at?: string;
          id?: string;
          ingestion_job_id?: string | null;
          metadata?: Json;
          playlist_item_id?: string | null;
          skip_reason?: string | null;
          source_added_at?: string | null;
          status?: string;
          updated_at?: string;
          user_id: string;
          youtube_video_id: string;
        };
        Update: {
          capture_source_id?: string;
          discovered_at?: string;
          id?: string;
          ingestion_job_id?: string | null;
          metadata?: Json;
          playlist_item_id?: string | null;
          skip_reason?: string | null;
          source_added_at?: string | null;
          status?: string;
          updated_at?: string;
          user_id?: string;
          youtube_video_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'youtube_capture_items_capture_source_id_fkey';
            columns: ['capture_source_id'];
            isOneToOne: false;
            referencedRelation: 'youtube_capture_sources';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'youtube_capture_items_ingestion_job_id_fkey';
            columns: ['ingestion_job_id'];
            isOneToOne: false;
            referencedRelation: 'ingestion_jobs';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'youtube_capture_items_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      youtube_capture_sources: {
        Row: {
          created_at: string;
          created_by: string;
          created_by_client: string | null;
          external_id: string;
          id: string;
          last_error: string | null;
          last_seen_item_at: string | null;
          last_synced_at: string | null;
          metadata: Json;
          source_type: string;
          source_url: string;
          status: string;
          sync_cadence_minutes: number;
          title: string;
          updated_at: string;
          user_id: string;
          visibility: string;
        };
        Insert: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          external_id: string;
          id?: string;
          last_error?: string | null;
          last_seen_item_at?: string | null;
          last_synced_at?: string | null;
          metadata?: Json;
          source_type?: string;
          source_url: string;
          status?: string;
          sync_cadence_minutes?: number;
          title?: string;
          updated_at?: string;
          user_id: string;
          visibility?: string;
        };
        Update: {
          created_at?: string;
          created_by?: string;
          created_by_client?: string | null;
          external_id?: string;
          id?: string;
          last_error?: string | null;
          last_seen_item_at?: string | null;
          last_synced_at?: string | null;
          metadata?: Json;
          source_type?: string;
          source_url?: string;
          status?: string;
          sync_cadence_minutes?: number;
          title?: string;
          updated_at?: string;
          user_id?: string;
          visibility?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'youtube_capture_sources_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      search_chunks: {
        Args: {
          category_filters?: Json;
          match_limit?: number;
          match_user_id: string;
          min_start_seconds?: number;
          query_embedding: string;
        };
        Returns: {
          access_reason: string;
          access_scope: string;
          access_source: string;
          channel_name: string;
          content: string;
          end_seconds: number;
          similarity: number;
          start_seconds: number;
          thumbnail_url: string;
          title: string;
          youtube_video_id: string;
        }[];
      };
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
};

type DatabaseWithoutInternals = Omit<Database, '__InternalSupabase'>;

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, 'public'>];

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema['Tables'] & DefaultSchema['Views'])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables'] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Views'])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables'] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Views'])[TableName] extends {
      Row: infer R;
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema['Tables'] & DefaultSchema['Views'])
    ? (DefaultSchema['Tables'] & DefaultSchema['Views'])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R;
      }
      ? R
      : never
    : never;

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema['Tables']
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables']
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables'][TableName] extends {
      Insert: infer I;
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema['Tables']
    ? DefaultSchema['Tables'][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I;
      }
      ? I
      : never
    : never;

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema['Tables']
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables']
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables'][TableName] extends {
      Update: infer U;
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema['Tables']
    ? DefaultSchema['Tables'][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U;
      }
      ? U
      : never
    : never;

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema['Enums']
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions['schema']]['Enums']
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions['schema']]['Enums'][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema['Enums']
    ? DefaultSchema['Enums'][DefaultSchemaEnumNameOrOptions]
    : never;

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema['CompositeTypes']
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions['schema']]['CompositeTypes']
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions['schema']]['CompositeTypes'][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema['CompositeTypes']
    ? DefaultSchema['CompositeTypes'][PublicCompositeTypeNameOrOptions]
    : never;

export const Constants = {
  graphql_public: {
    Enums: {},
  },
  public: {
    Enums: {},
  },
} as const;
