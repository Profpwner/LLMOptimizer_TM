import axios from 'axios';
import { Template, ContentType } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

class TemplateService {
  private apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  constructor() {
    // Add auth token to requests if available
    this.apiClient.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  async fetchTemplates(): Promise<Template[]> {
    try {
      const response = await this.apiClient.get('/templates');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch templates from server, using mock data', error);
      return this.getMockTemplates();
    }
  }

  async getTemplate(templateId: string): Promise<Template> {
    try {
      const response = await this.apiClient.get(`/templates/${templateId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch template', error);
      throw error;
    }
  }

  async getTemplatesByCategory(category: ContentType): Promise<Template[]> {
    try {
      const response = await this.apiClient.get('/templates', {
        params: { category },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch templates by category', error);
      throw error;
    }
  }

  async getRecommendedTemplates(userId: string): Promise<Template[]> {
    try {
      const response = await this.apiClient.get(`/templates/recommended/${userId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch recommended templates', error);
      return [];
    }
  }

  async applyTemplate(templateId: string, customizations?: any): Promise<any> {
    try {
      const response = await this.apiClient.post(`/templates/${templateId}/apply`, {
        customizations,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to apply template', error);
      throw error;
    }
  }

  async saveAsTemplate(name: string, content: any, category: ContentType): Promise<Template> {
    try {
      const response = await this.apiClient.post('/templates', {
        name,
        content,
        category,
        isCustom: true,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to save as template', error);
      throw error;
    }
  }

  async deleteTemplate(templateId: string): Promise<void> {
    try {
      await this.apiClient.delete(`/templates/${templateId}`);
    } catch (error) {
      console.error('Failed to delete template', error);
      throw error;
    }
  }

  async rateTemplate(templateId: string, rating: number): Promise<void> {
    try {
      await this.apiClient.post(`/templates/${templateId}/rate`, { rating });
    } catch (error) {
      console.error('Failed to rate template', error);
    }
  }

  // Mock data for development/demo
  private getMockTemplates(): Template[] {
    return [
      {
        id: '1',
        name: 'SEO-Optimized Blog Post',
        description: 'A comprehensive blog post template optimized for search engines with proper heading structure and keyword placement.',
        category: ContentType.BLOG,
        industry: 'Technology',
        thumbnail: '/images/templates/blog-seo.png',
        previewUrl: '/templates/preview/blog-seo',
        features: [
          'SEO-friendly heading structure',
          'Meta description generator',
          'Keyword density analyzer',
          'Readability score optimization',
          'Internal linking suggestions',
        ],
        difficulty: 'beginner',
        estimatedTime: '30 mins',
        popularity: 95,
        tags: ['seo', 'blog', 'content', 'writing'],
        content: {
          structure: {
            title: '',
            metaDescription: '',
            introduction: '',
            mainSections: [],
            conclusion: '',
            cta: '',
          },
          defaultValues: {
            wordCount: 1500,
            readabilityTarget: 60,
            keywordDensity: 2,
          },
          customizations: [
            {
              id: 'tone',
              label: 'Writing Tone',
              type: 'select',
              options: ['professional', 'casual', 'technical', 'conversational'],
              defaultValue: 'professional',
            },
            {
              id: 'includeImages',
              label: 'Include Image Placeholders',
              type: 'boolean',
              defaultValue: true,
            },
          ],
        },
      },
      {
        id: '2',
        name: 'Product Description Pro',
        description: 'Create compelling product descriptions that highlight features, benefits, and drive conversions.',
        category: ContentType.PRODUCT,
        industry: 'E-commerce',
        thumbnail: '/images/templates/product-desc.png',
        previewUrl: '/templates/preview/product-desc',
        features: [
          'Feature-benefit framework',
          'Emotional triggers',
          'Social proof integration',
          'Call-to-action optimization',
          'Mobile-friendly formatting',
        ],
        difficulty: 'intermediate',
        estimatedTime: '20 mins',
        popularity: 88,
        tags: ['ecommerce', 'product', 'sales', 'conversion'],
        content: {
          structure: {
            headline: '',
            subheadline: '',
            features: [],
            benefits: [],
            specifications: [],
            socialProof: '',
            cta: '',
          },
          defaultValues: {
            featureCount: 5,
            wordLimit: 300,
          },
          customizations: [
            {
              id: 'productType',
              label: 'Product Type',
              type: 'select',
              options: ['physical', 'digital', 'service', 'subscription'],
              defaultValue: 'physical',
            },
            {
              id: 'urgency',
              label: 'Include Urgency Elements',
              type: 'boolean',
              defaultValue: false,
            },
          ],
        },
      },
      {
        id: '3',
        name: 'Landing Page Converter',
        description: 'High-converting landing page template with A/B testing ready variations.',
        category: ContentType.LANDING,
        industry: 'Marketing',
        thumbnail: '/images/templates/landing-page.png',
        previewUrl: '/templates/preview/landing-page',
        features: [
          'Hero section optimization',
          'Trust signals placement',
          'Conversion-focused copy',
          'Mobile responsiveness',
          'A/B test variations',
        ],
        difficulty: 'advanced',
        estimatedTime: '45 mins',
        popularity: 92,
        tags: ['landing', 'conversion', 'marketing', 'ab-testing'],
        content: {
          structure: {
            hero: {
              headline: '',
              subheadline: '',
              cta: '',
            },
            features: [],
            testimonials: [],
            faq: [],
            finalCta: '',
          },
          defaultValues: {
            colorScheme: 'blue',
            layout: 'centered',
          },
          customizations: [
            {
              id: 'goal',
              label: 'Primary Goal',
              type: 'select',
              options: ['lead-generation', 'sale', 'signup', 'download'],
              defaultValue: 'lead-generation',
            },
            {
              id: 'formFields',
              label: 'Number of Form Fields',
              type: 'number',
              defaultValue: 3,
            },
          ],
        },
      },
    ];
  }
}

export const templateService = new TemplateService();

// Export the fetch function for the Redux thunk
export const fetchTemplates = () => templateService.fetchTemplates();