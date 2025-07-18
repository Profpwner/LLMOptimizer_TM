import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

const CONTENT_SERVICE_URL = process.env.REACT_APP_CONTENT_SERVICE_URL || 'http://localhost:8002';

interface ContentCreateRequest {
  title: string;
  content_type: string;
  original_content: string;
  target_audience?: string;
  keywords?: string[];
  metadata?: Record<string, any>;
}

interface ContentResponse {
  id: string;
  user_id: string;
  title: string;
  content_type: string;
  original_content: string;
  optimized_content?: string;
  target_audience?: string;
  keywords: string[];
  metadata: Record<string, any>;
  status: string;
  optimization_score?: number;
  created_at: string;
  updated_at: string;
}

interface URLSubmitRequest {
  urls: string[];
  content_type: string;
  metadata?: Record<string, any>;
}

interface URLSubmitResponse {
  job_id: string;
  status: string;
  results?: Array<{
    url: string;
    success: boolean;
    content_id?: string;
    error?: string;
  }>;
}

interface BatchUploadResponse {
  job_id: string;
  status: string;
  items_processed: number;
  items_failed: number;
  errors?: string[];
}

export const contentApi = createApi({
  reducerPath: 'contentApi',
  baseQuery: fetchBaseQuery({
    baseUrl: CONTENT_SERVICE_URL,
    prepareHeaders: (headers) => {
      // Get auth token from localStorage or Redux store
      const token = localStorage.getItem('authToken');
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  tagTypes: ['Content'],
  endpoints: (builder) => ({
    // Create content
    createContent: builder.mutation<ContentResponse, ContentCreateRequest>({
      query: (data) => ({
        url: '/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Content'],
    }),

    // Get content list
    getContentList: builder.query<{
      items: ContentResponse[];
      total: number;
      page: number;
      page_size: number;
    }, {
      page?: number;
      page_size?: number;
      status?: string;
      content_type?: string;
    }>({
      query: (params) => ({
        url: '/',
        params,
      }),
      providesTags: ['Content'],
    }),

    // Get single content
    getContent: builder.query<ContentResponse, string>({
      query: (id) => `/${id}`,
      providesTags: (result, error, id) => [{ type: 'Content', id }],
    }),

    // Update content
    updateContent: builder.mutation<ContentResponse, {
      id: string;
      data: Partial<ContentCreateRequest>;
    }>({
      query: ({ id, data }) => ({
        url: `/${id}`,
        method: 'PUT',
        body: data,
      }),
      invalidatesTags: (result, error, { id }) => [{ type: 'Content', id }],
    }),

    // Delete content
    deleteContent: builder.mutation<{ message: string }, string>({
      query: (id) => ({
        url: `/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Content'],
    }),

    // Submit URLs for content extraction
    submitURLs: builder.mutation<URLSubmitResponse, URLSubmitRequest>({
      query: (data) => ({
        url: '/api/content_input/urls',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Content'],
    }),

    // Upload batch file
    uploadBatch: builder.mutation<BatchUploadResponse, FormData>({
      query: (formData) => ({
        url: '/api/content_input/batch',
        method: 'POST',
        body: formData,
      }),
      invalidatesTags: ['Content'],
    }),

    // Get job status (for tracking batch/URL processing)
    getJobStatus: builder.query<{
      job_id: string;
      status: string;
      progress: number;
      result?: any;
      error?: string;
    }, string>({
      query: (jobId) => `/api/jobs/${jobId}`,
    }),

    // Get content processing status via WebSocket updates
    subscribeToContentUpdates: builder.mutation<void, string>({
      queryFn: async (contentId) => {
        // This would typically establish a WebSocket connection
        // Implementation depends on your WebSocket setup
        return { data: undefined };
      },
    }),
  }),
});

export const {
  useCreateContentMutation,
  useGetContentListQuery,
  useGetContentQuery,
  useUpdateContentMutation,
  useDeleteContentMutation,
  useSubmitURLsMutation,
  useUploadBatchMutation,
  useGetJobStatusQuery,
  useSubscribeToContentUpdatesMutation,
} = contentApi;