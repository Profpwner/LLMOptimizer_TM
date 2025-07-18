# LLM Optimizer - Onboarding System

A comprehensive React-based onboarding system for the LLM Optimizer platform, featuring interactive product tours, multi-step wizards, template libraries, and progress tracking.

## Features

### 1. **Onboarding Flow Architecture**
- User journey mapping with state management
- Progress tracking and persistence
- Skip/resume functionality
- Analytics integration
- Role-based customization

### 2. **Interactive Product Tour**
- Built with React Joyride
- Dynamic step targeting
- Customizable tooltips with actions
- Role-specific tour variations
- Progress tracking

### 3. **Optimization Wizard**
- Multi-step form with validation (React Hook Form + Yup)
- Progress indicators
- Data persistence between steps
- Contextual help system
- Review and confirmation step

### 4. **Template Library**
- Categorized templates (Blog, Product, FAQ, Social, etc.)
- Industry-specific filtering
- Advanced search with Fuse.js
- Template preview system
- One-click template application

### 5. **Onboarding Dashboard**
- Welcome screen with personalized greeting
- Progress overview with visual indicators
- Quick action cards
- Resource links
- Achievement badges system

## Tech Stack

- **React 18** with TypeScript
- **Redux Toolkit** for state management
- **Material-UI (MUI)** for UI components
- **React Router** for navigation
- **React Joyride** for product tours
- **React Hook Form** with Yup for form validation
- **Framer Motion** for animations
- **Notistack** for notifications
- **Fuse.js** for fuzzy search

## Project Structure

```
frontend/onboarding/
├── public/                    # Static assets
├── src/
│   ├── components/           # React components
│   │   ├── OnboardingDashboard/
│   │   ├── OptimizationWizard/
│   │   ├── ProductTour/
│   │   └── TemplateLibrary/
│   ├── hooks/                # Custom React hooks
│   ├── services/             # API services
│   ├── store/                # Redux store and slices
│   ├── types/                # TypeScript definitions
│   ├── utils/                # Utility functions
│   └── App.tsx               # Main application component
└── package.json
```

## Installation

```bash
cd frontend/onboarding
npm install
```

## Development

```bash
npm start
```

The app will run on [http://localhost:3000](http://localhost:3000)

## Key Components

### OnboardingDashboard
Central hub for new users featuring:
- Progress tracking
- Quick actions
- Achievement system
- Resource links

### OptimizationWizard
Multi-step wizard collecting:
- User information
- Business details
- Optimization goals
- Preferences

### ProductTour
Interactive tour system with:
- Spotlight highlighting
- Step-by-step guidance
- Custom tooltips
- Action triggers

### TemplateLibrary
Template management with:
- Category filtering
- Search functionality
- Preview system
- Apply functionality

## State Management

The application uses Redux Toolkit with the following slices:

- `onboardingSlice`: Main onboarding flow state
- `tourSlice`: Product tour state
- `templateSlice`: Template library state
- `userSlice`: User information
- `analyticsSlice`: Analytics tracking

## API Integration

Services are provided for:
- Progress tracking
- Template fetching
- Analytics events
- User preferences

## Customization

### Adding New Tour Steps

Edit `src/utils/tourSteps.tsx`:

```typescript
const newStep: TourStep = {
  target: '.element-selector',
  content: 'Step description',
  placement: 'bottom',
  title: 'Step Title'
};
```

### Adding Wizard Steps

1. Create a new step component in `src/components/OptimizationWizard/steps/`
2. Add to the steps array in `OptimizationWizard/index.tsx`

### Creating Templates

Templates can be added via the template service or API.

## Analytics

The system tracks:
- Step completion
- Time spent
- Feature usage
- Drop-off points
- User interactions

## Accessibility

- ARIA labels and roles
- Keyboard navigation
- Screen reader support
- Focus management
- Color contrast compliance

## Mobile Responsiveness

- Responsive grid layouts
- Touch-friendly interactions
- Mobile-optimized tours
- Adaptive UI components

## Future Enhancements

1. A/B testing for onboarding flows
2. Video tutorials integration
3. Gamification elements
4. Multi-language support
5. Advanced analytics dashboard