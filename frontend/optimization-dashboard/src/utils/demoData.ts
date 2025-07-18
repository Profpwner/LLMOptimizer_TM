import { OptimizationResult, Platform } from '../types';

export const generateDemoData = (): OptimizationResult => {
  const platforms: Platform[] = ['ChatGPT', 'Claude', 'Gemini', 'Perplexity'];
  
  return {
    id: 'demo-result-1',
    contentId: 'demo-content',
    createdAt: new Date().toISOString(),
    status: 'completed',
    visibility: {
      overall: 78,
      timestamp: new Date().toISOString(),
      platforms: platforms.map(platform => ({
        platform,
        score: Math.floor(Math.random() * 30) + 70,
        change: Math.floor(Math.random() * 20) - 10,
        details: {
          keywords: Math.floor(Math.random() * 30) + 70,
          structure: Math.floor(Math.random() * 30) + 70,
          readability: Math.floor(Math.random() * 30) + 70,
          engagement: Math.floor(Math.random() * 30) + 70,
        },
      })),
    },
    comparison: {
      original: `# Understanding LLM Optimization

Large Language Models (LLMs) have revolutionized natural language processing. This article explores optimization techniques for better visibility across AI platforms.

## Key Concepts

LLMs process text using transformer architectures. Understanding their ranking mechanisms is crucial for content optimization.

### Technical Details

The attention mechanism allows models to focus on relevant parts of the input, creating contextual embeddings that capture semantic meaning.`,
      optimized: `# Understanding LLM Optimization: A Comprehensive Guide

Large Language Models (LLMs) have fundamentally transformed natural language processing and AI-driven content discovery. This comprehensive article explores cutting-edge optimization techniques to maximize your content's visibility across major AI platforms including ChatGPT, Claude, Gemini, and Perplexity.

## Key Concepts in LLM Optimization

Modern LLMs leverage sophisticated transformer architectures to process and understand text. Mastering their ranking mechanisms is essential for effective content optimization in 2024.

### Technical Implementation Details

The multi-head attention mechanism enables models to dynamically focus on the most relevant portions of input text, generating rich contextual embeddings that capture nuanced semantic relationships and meaning.

**Key optimization factors include:**
- Semantic relevance and keyword density
- Structural clarity and logical flow
- Readability scores and engagement metrics
- Technical accuracy and depth of coverage`,
      changes: [
        { type: 'equal', value: '# Understanding LLM Optimization' },
        { type: 'add', value: ': A Comprehensive Guide' },
        { type: 'equal', value: '\n\nLarge Language Models (LLMs) have ' },
        { type: 'remove', value: 'revolutionized' },
        { type: 'add', value: 'fundamentally transformed' },
        { type: 'equal', value: ' natural language processing' },
        { type: 'add', value: ' and AI-driven content discovery' },
        { type: 'equal', value: '. This ' },
        { type: 'add', value: 'comprehensive ' },
        { type: 'equal', value: 'article explores ' },
        { type: 'add', value: 'cutting-edge ' },
        { type: 'equal', value: 'optimization techniques ' },
        { type: 'remove', value: 'for better' },
        { type: 'add', value: 'to maximize your content\'s' },
        { type: 'equal', value: ' visibility across ' },
        { type: 'add', value: 'major ' },
        { type: 'equal', value: 'AI platforms' },
        { type: 'add', value: ' including ChatGPT, Claude, Gemini, and Perplexity' },
        { type: 'equal', value: '.' },
      ],
      stats: {
        charactersAdded: 287,
        charactersRemoved: 42,
        wordsAdded: 43,
        wordsRemoved: 6,
      },
    },
    suggestions: [
      {
        id: 'sug-1',
        title: 'Add platform-specific keywords',
        description: 'Include keywords that are highly relevant to each AI platform\'s training data',
        category: 'keyword',
        priority: 'high',
        impact: 25,
        platform: 'ChatGPT',
        implementation: {
          type: 'automatic',
          code: 'content.replace(/AI/g, "artificial intelligence AI")',
        },
        status: 'pending',
      },
      {
        id: 'sug-2',
        title: 'Improve heading structure',
        description: 'Use hierarchical heading structure with descriptive H2 and H3 tags',
        category: 'structure',
        priority: 'medium',
        impact: 15,
        implementation: {
          type: 'manual',
          instructions: 'Review and restructure headings to follow a clear hierarchy',
        },
        status: 'pending',
      },
      {
        id: 'sug-3',
        title: 'Enhance readability score',
        description: 'Simplify complex sentences and use shorter paragraphs',
        category: 'readability',
        priority: 'medium',
        impact: 18,
        implementation: {
          type: 'automatic',
        },
        status: 'pending',
      },
      {
        id: 'sug-4',
        title: 'Add code examples',
        description: 'Include practical code snippets to improve technical relevance',
        category: 'technical',
        priority: 'high',
        impact: 22,
        platform: 'Claude',
        implementation: {
          type: 'manual',
          instructions: 'Add 2-3 code examples demonstrating key concepts',
        },
        status: 'pending',
      },
      {
        id: 'sug-5',
        title: 'Increase engagement elements',
        description: 'Add questions, examples, and interactive elements',
        category: 'engagement',
        priority: 'low',
        impact: 12,
        implementation: {
          type: 'automatic',
        },
        status: 'pending',
      },
    ],
    metrics: {
      visibility: {
        id: 'vis-1',
        name: 'Visibility Score',
        value: 78,
        previousValue: 65,
        unit: '%',
        trend: 'up',
        change: 13,
        changePercent: 20,
        target: 85,
        description: 'Overall visibility across AI platforms',
      },
      engagement: {
        id: 'eng-1',
        name: 'Engagement Rate',
        value: 4.2,
        previousValue: 3.5,
        unit: '%',
        trend: 'up',
        change: 0.7,
        changePercent: 20,
        target: 5.0,
        description: 'User engagement with optimized content',
      },
      conversion: {
        id: 'conv-1',
        name: 'Conversion Rate',
        value: 2.8,
        previousValue: 2.1,
        unit: '%',
        trend: 'up',
        change: 0.7,
        changePercent: 33.3,
        target: 3.5,
        description: 'Conversion from views to actions',
      },
      reach: {
        id: 'reach-1',
        name: 'Audience Reach',
        value: 15420,
        previousValue: 12100,
        unit: 'users',
        trend: 'up',
        change: 3320,
        changePercent: 27.4,
        target: 20000,
        description: 'Total unique users reached',
      },
      performance: {
        id: 'perf-1',
        name: 'Performance Score',
        value: 92,
        previousValue: 88,
        unit: '%',
        trend: 'up',
        change: 4,
        changePercent: 4.5,
        target: 95,
        description: 'Content loading and rendering performance',
      },
    },
  };
};

export const generateHistoricalData = (count: number = 50) => {
  const data = [];
  const now = new Date();
  
  for (let i = 0; i < count; i++) {
    const timestamp = new Date(now.getTime() - i * 60 * 60 * 1000); // 1 hour intervals
    data.push({
      timestamp: timestamp.toISOString(),
      metrics: {
        visibility: {
          id: 'vis-hist',
          name: 'Visibility',
          value: Math.floor(Math.random() * 20) + 70,
          previousValue: 0,
          unit: '%',
          trend: 'stable' as const,
          change: 0,
          changePercent: 0,
        },
        engagement: {
          id: 'eng-hist',
          name: 'Engagement',
          value: Math.random() * 2 + 3,
          previousValue: 0,
          unit: '%',
          trend: 'stable' as const,
          change: 0,
          changePercent: 0,
        },
        conversion: {
          id: 'conv-hist',
          name: 'Conversion',
          value: Math.random() * 1.5 + 2,
          previousValue: 0,
          unit: '%',
          trend: 'stable' as const,
          change: 0,
          changePercent: 0,
        },
        reach: {
          id: 'reach-hist',
          name: 'Reach',
          value: Math.floor(Math.random() * 5000) + 10000,
          previousValue: 0,
          unit: 'users',
          trend: 'stable' as const,
          change: 0,
          changePercent: 0,
        },
        performance: {
          id: 'perf-hist',
          name: 'Performance',
          value: Math.floor(Math.random() * 10) + 85,
          previousValue: 0,
          unit: '%',
          trend: 'stable' as const,
          change: 0,
          changePercent: 0,
        },
      },
    });
  }
  
  return data.reverse();
};