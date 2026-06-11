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
      profiles: {
        Row: {
          api_key_enc: string | null;
          avatar_url: string | null;
          created_at: string;
          display_name: string | null;
          free_indexes_this_month: number;
          free_indexed_seconds_total: number;
          free_indexed_videos_total: number;
          free_searches_this_month: number;
          free_searches_today: number;
          id: string;
          last_index_reset: string;
          last_search_month_reset: string;
          last_search_reset: string;
        };
        Insert: {
          api_key_enc?: string | null;
          avatar_url?: string | null;
          created_at?: string;
          display_name?: string | null;
          free_indexes_this_month?: number;
          free_indexed_seconds_total?: number;
          free_indexed_videos_total?: number;
          free_searches_this_month?: number;
          free_searches_today?: number;
          id: string;
          last_index_reset?: string;
          last_search_month_reset?: string;
          last_search_reset?: string;
        };
        Update: {
          api_key_enc?: string | null;
          avatar_url?: string | null;
          created_at?: string;
          display_name?: string | null;
          free_indexes_this_month?: number;
          free_indexed_seconds_total?: number;
          free_indexed_videos_total?: number;
          free_searches_this_month?: number;
          free_searches_today?: number;
          id?: string;
          last_index_reset?: string;
          last_search_month_reset?: string;
          last_search_reset?: string;
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
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      [_ in never]: never;
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
