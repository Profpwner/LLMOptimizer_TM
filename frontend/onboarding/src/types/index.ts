// User types
export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  createdAt: Date;
  onboardingCompleted: boolean;
  preferences?: UserPreferences;
}

export enum UserRole {
  MARKETER = 'marketer',
  CONTENT_CREATOR = 'content_creator',
  SEO_SPECIALIST = 'seo_specialist',
  BUSINESS_OWNER = 'business_owner',
  DEVELOPER = 'developer'
}

export interface UserPreferences {
  industry?: string;
  contentTypes?: ContentType[];
  primaryGoals?: OptimizationGoal[];
  experience?: ExperienceLevel;
}

export enum ContentType {
  BLOG = 'blog',
  PRODUCT = 'product',
  LANDING = 'landing',
  FAQ = 'faq',
  SOCIAL = 'social',
  EMAIL = 'email'
}

export enum OptimizationGoal {
  SEO_RANKING = 'seo_ranking',
  ENGAGEMENT = 'engagement',
  CONVERSION = 'conversion',
  READABILITY = 'readability',
  BRAND_VOICE = 'brand_voice'
}

export enum ExperienceLevel {
  BEGINNER = 'beginner',
  INTERMEDIATE = 'intermediate',
  ADVANCED = 'advanced'
}

// Onboarding types
export interface OnboardingState {
  currentStep: number;
  totalSteps: number;
  completedSteps: string[];
  skippedSteps: string[];
  startedAt?: Date;
  completedAt?: Date;
  progress: number;
  tourActive: boolean;
  wizardData: WizardData;
}

export interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  component: React.ComponentType<any>;
  isOptional?: boolean;
  dependencies?: string[];
  analytics?: AnalyticsEvent;
}

export interface WizardData {
  userInfo?: {
    name: string;
    role: UserRole;
    experience: ExperienceLevel;
  };
  businessInfo?: {
    industry: string;
    companySize: string;
    website?: string;
  };
  goals?: {
    primaryGoals: OptimizationGoal[];
    contentTypes: ContentType[];
    monthlyVolume?: string;
  };
  preferences?: {
    features: string[];
    integrations: string[];
    notifications: boolean;
  };
  selectedTemplate?: Template;
}

// Product Tour types
export interface TourStep {
  target: string;
  content: React.ReactNode;
  placement?: 'top' | 'bottom' | 'left' | 'right' | 'center';
  disableBeacon?: boolean;
  disableOverlay?: boolean;
  spotlightClicks?: boolean;
  styles?: object;
  title?: string;
  hideCloseButton?: boolean;
  hideFooter?: boolean;
  showProgress?: boolean;
  showSkipButton?: boolean;
  actions?: TourAction[];
}

export interface TourAction {
  label: string;
  action: () => void;
  primary?: boolean;
}

export interface TourState {
  run: boolean;
  stepIndex: number;
  steps: TourStep[];
  tourId: string;
  completed: boolean;
}

// Template types
export interface Template {
  id: string;
  name: string;
  description: string;
  category: ContentType;
  industry?: string;
  thumbnail?: string;
  previewUrl?: string;
  features: string[];
  difficulty: ExperienceLevel;
  estimatedTime: string;
  popularity: number;
  tags: string[];
  content: TemplateContent;
}

export interface TemplateContent {
  structure: any;
  defaultValues: Record<string, any>;
  customizations: TemplateCustomization[];
}

export interface TemplateCustomization {
  id: string;
  label: string;
  type: 'text' | 'select' | 'color' | 'number' | 'boolean';
  options?: any[];
  defaultValue: any;
}

// Analytics types
export interface AnalyticsEvent {
  name: string;
  category: 'onboarding' | 'tour' | 'wizard' | 'template';
  properties?: Record<string, any>;
}

export interface OnboardingAnalytics {
  userId: string;
  sessionId: string;
  events: AnalyticsEventLog[];
  metrics: OnboardingMetrics;
}

export interface AnalyticsEventLog {
  event: AnalyticsEvent;
  timestamp: Date;
  context?: Record<string, any>;
}

export interface OnboardingMetrics {
  totalTime: number;
  completionRate: number;
  stepsCompleted: number;
  stepsSkipped: number;
  tourCompleted: boolean;
  wizardCompleted: boolean;
  templateSelected: boolean;
  dropoffStep?: string;
}

// Achievement types
export interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: 'onboarding' | 'usage' | 'milestone' | 'special';
  points: number;
  unlockedAt?: Date;
  requirements: AchievementRequirement[];
}

export interface AchievementRequirement {
  type: 'complete_step' | 'use_feature' | 'reach_milestone';
  target: string;
  value: number;
  current?: number;
}