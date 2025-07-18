// Platform types
export type Platform = 'ChatGPT' | 'Claude' | 'Gemini' | 'Perplexity';

// Visibility Score types
export interface PlatformScore {
  platform: Platform;
  score: number;
  change: number;
  details: {
    keywords: number;
    structure: number;
    readability: number;
    engagement: number;
  };
}

export interface VisibilityData {
  overall: number;
  platforms: PlatformScore[];
  timestamp: string;
}

// Content Comparison types
export interface ContentDiff {
  original: string;
  optimized: string;
  changes: DiffChange[];
  stats: {
    charactersAdded: number;
    charactersRemoved: number;
    wordsAdded: number;
    wordsRemoved: number;
  };
}

export interface DiffChange {
  type: 'add' | 'remove' | 'equal';
  value: string;
  lineNumber?: number;
}

// Suggestions types
export interface Suggestion {
  id: string;
  title: string;
  description: string;
  category: 'keyword' | 'structure' | 'readability' | 'technical' | 'engagement';
  priority: 'high' | 'medium' | 'low';
  impact: number;
  platform?: Platform;
  implementation?: {
    type: 'automatic' | 'manual';
    code?: string;
    instructions?: string;
  };
  status: 'pending' | 'applied' | 'rejected';
}

// Impact Metrics types
export interface Metric {
  id: string;
  name: string;
  value: number;
  previousValue: number;
  unit: string;
  trend: 'up' | 'down' | 'stable';
  change: number;
  changePercent: number;
  target?: number;
  description?: string;
}

export interface ImpactMetrics {
  visibility: Metric;
  engagement: Metric;
  conversion: Metric;
  reach: Metric;
  performance: Metric;
  custom?: Metric[];
}

// Dashboard State types
export interface OptimizationResult {
  id: string;
  contentId: string;
  createdAt: string;
  visibility: VisibilityData;
  comparison: ContentDiff;
  suggestions: Suggestion[];
  metrics: ImpactMetrics;
  status: 'processing' | 'completed' | 'error';
  error?: string;
}

export interface DashboardState {
  results: OptimizationResult | null;
  loading: boolean;
  error: string | null;
  selectedPlatform: Platform | 'all';
  filters: {
    suggestionCategories: string[];
    suggestionPriorities: string[];
    suggestionStatus: string[];
  };
  viewMode: 'split' | 'unified';
}