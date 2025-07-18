import { useCallback, useEffect, useMemo } from 'react';
import { useAppDispatch, useAppSelector } from './index';
import {
  loadTemplates,
  selectTemplate,
  clearSelectedTemplate,
  setFilter,
  clearFilters,
  applyTemplate,
} from '../store/slices/templateSlice';
import { logEvent, setTemplateSelected } from '../store/slices/analyticsSlice';
import { Template, ContentType } from '../types';
import Fuse from 'fuse.js';

export const useTemplates = () => {
  const dispatch = useAppDispatch();
  const { templates, selectedTemplate, loading, error, filters } = useAppSelector((state) => state.template);
  const user = useAppSelector((state) => state.user.currentUser);

  // Load templates on mount
  useEffect(() => {
    dispatch(loadTemplates());
  }, [dispatch]);

  // Set up fuzzy search
  const fuse = useMemo(() => {
    return new Fuse(templates, {
      keys: ['name', 'description', 'tags', 'category', 'industry'],
      threshold: 0.3,
      includeScore: true,
    });
  }, [templates]);

  // Filter and search templates
  const filteredTemplates = useMemo(() => {
    let result = [...templates];

    // Apply category filter
    if (filters.category) {
      result = result.filter(t => t.category === filters.category);
    }

    // Apply industry filter
    if (filters.industry) {
      result = result.filter(t => t.industry === filters.industry);
    }

    // Apply search
    if (filters.searchQuery) {
      const searchResults = fuse.search(filters.searchQuery);
      result = searchResults.map(r => r.item);
    }

    // Apply sorting
    switch (filters.sortBy) {
      case 'popularity':
        result.sort((a, b) => b.popularity - a.popularity);
        break;
      case 'name':
        result.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'difficulty':
        const difficultyOrder = { beginner: 0, intermediate: 1, advanced: 2 };
        result.sort((a, b) => difficultyOrder[a.difficulty] - difficultyOrder[b.difficulty]);
        break;
    }

    return result;
  }, [templates, filters, fuse]);

  const select = useCallback((template: Template) => {
    dispatch(selectTemplate(template));
    dispatch(logEvent({
      event: {
        name: 'template_selected',
        category: 'template',
        properties: {
          templateId: template.id,
          templateName: template.name,
          category: template.category,
          userId: user?.id,
        },
      },
    }));
  }, [dispatch, user?.id]);

  const clearSelection = useCallback(() => {
    dispatch(clearSelectedTemplate());
  }, [dispatch]);

  const apply = useCallback((templateId: string) => {
    dispatch(applyTemplate(templateId));
    dispatch(setTemplateSelected());
    dispatch(logEvent({
      event: {
        name: 'template_applied',
        category: 'template',
        properties: {
          templateId,
          userId: user?.id,
        },
      },
    }));
  }, [dispatch, user?.id]);

  const updateFilter = useCallback((filterUpdate: Partial<typeof filters>) => {
    dispatch(setFilter(filterUpdate));
  }, [dispatch]);

  const resetFilters = useCallback(() => {
    dispatch(clearFilters());
  }, [dispatch]);

  // Get unique values for filters
  const filterOptions = useMemo(() => {
    const categories = Array.from(new Set(templates.map(t => t.category)));
    const industries = Array.from(new Set(templates.map(t => t.industry).filter(Boolean))) as string[];
    const tags = Array.from(new Set(templates.flatMap(t => t.tags)));

    return {
      categories,
      industries,
      tags,
    };
  }, [templates]);

  // Get templates by category
  const getTemplatesByCategory = useCallback((category: ContentType): Template[] => {
    return templates.filter(t => t.category === category);
  }, [templates]);

  // Get recommended templates based on user preferences
  const recommendedTemplates = useMemo(() => {
    if (!user?.preferences) return templates.slice(0, 6);

    return templates
      .filter(t => {
        // Filter by user's content types
        if (user.preferences?.contentTypes?.includes(t.category)) return true;
        // Filter by user's industry
        if (user.preferences?.industry === t.industry) return true;
        // Filter by experience level
        if (user.preferences?.experience === t.difficulty) return true;
        return false;
      })
      .sort((a, b) => b.popularity - a.popularity)
      .slice(0, 6);
  }, [templates, user]);

  return {
    templates: filteredTemplates,
    allTemplates: templates,
    selectedTemplate,
    loading,
    error,
    filters,
    filterOptions,
    recommendedTemplates,
    select,
    clearSelection,
    apply,
    updateFilter,
    resetFilters,
    getTemplatesByCategory,
  };
};