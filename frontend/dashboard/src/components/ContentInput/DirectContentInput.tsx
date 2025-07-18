import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Paper,
  Typography,
  Alert,
  CircularProgress,
  Divider,
  IconButton,
  Tooltip
} from '@mui/material';
import GridLegacyLegacy from '@mui/material/GridLegacyLegacy';
import SendIcon from '@mui/icons-material/Send';
import PreviewIcon from '@mui/icons-material/Preview';
import ClearIcon from '@mui/icons-material/Clear';
import { useCreateContentMutation } from '../../services/contentApi';
import ContentPreview from './ContentPreview';

// Simple rich text editor toolbar
const EditorToolbar: React.FC<{ editorRef: React.RefObject<HTMLDivElement> }> = ({ editorRef }) => {
  const execCommand = (command: string, value?: string) => {
    document.execCommand(command, false, value);
    editorRef.current?.focus();
  };

  return (
    <Box sx={{ 
      display: 'flex', 
      gap: 1, 
      p: 1, 
      borderBottom: 1, 
      borderColor: 'divider',
      flexWrap: 'wrap'
    }}>
      <Button size="small" onClick={() => execCommand('bold')}>Bold</Button>
      <Button size="small" onClick={() => execCommand('italic')}>Italic</Button>
      <Button size="small" onClick={() => execCommand('underline')}>Underline</Button>
      <Divider orientation="vertical" flexItem />
      <Button size="small" onClick={() => execCommand('insertUnorderedList')}>• List</Button>
      <Button size="small" onClick={() => execCommand('insertOrderedList')}>1. List</Button>
      <Divider orientation="vertical" flexItem />
      <Button size="small" onClick={() => execCommand('justifyLeft')}>Left</Button>
      <Button size="small" onClick={() => execCommand('justifyCenter')}>Center</Button>
      <Button size="small" onClick={() => execCommand('justifyRight')}>Right</Button>
      <Divider orientation="vertical" flexItem />
      <Select
        size="small"
        defaultValue="p"
        onChange={(e) => execCommand('formatBlock', e.target.value as string)}
      >
        <MenuItem value="p">Paragraph</MenuItem>
        <MenuItem value="h1">Heading 1</MenuItem>
        <MenuItem value="h2">Heading 2</MenuItem>
        <MenuItem value="h3">Heading 3</MenuItem>
      </Select>
    </Box>
  );
};

interface ContentFormData {
  title: string;
  contentType: string;
  content: string;
  targetAudience: string;
  keywords: string[];
}

export default function DirectContentInput() {
  const editorRef = useRef<HTMLDivElement>(null);
  const [formData, setFormData] = useState<ContentFormData>({
    title: '',
    contentType: 'article',
    content: '',
    targetAudience: '',
    keywords: []
  });
  const [currentKeyword, setCurrentKeyword] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createContent, { isLoading, isSuccess }] = useCreateContentMutation();

  // Update content from editor
  useEffect(() => {
    const handleInput = () => {
      if (editorRef.current) {
        setFormData(prev => ({
          ...prev,
          content: editorRef.current?.innerHTML || ''
        }));
      }
    };

    const editor = editorRef.current;
    if (editor) {
      editor.addEventListener('input', handleInput);
      return () => editor.removeEventListener('input', handleInput);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.title || !formData.content) {
      setError('Please provide both title and content');
      return;
    }

    try {
      await createContent({
        title: formData.title,
        content_type: formData.contentType,
        original_content: formData.content,
        target_audience: formData.targetAudience,
        keywords: formData.keywords,
        metadata: {
          source: 'direct_input',
          content_format: 'html'
        }
      }).unwrap();

      // Reset form on success
      setFormData({
        title: '',
        contentType: 'article',
        content: '',
        targetAudience: '',
        keywords: []
      });
      if (editorRef.current) {
        editorRef.current.innerHTML = '';
      }
    } catch (err: any) {
      setError(err.data?.detail || 'Failed to create content');
    }
  };

  const handleAddKeyword = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && currentKeyword.trim()) {
      e.preventDefault();
      setFormData(prev => ({
        ...prev,
        keywords: [...prev.keywords, currentKeyword.trim()]
      }));
      setCurrentKeyword('');
    }
  };

  const handleDeleteKeyword = (keywordToDelete: string) => {
    setFormData(prev => ({
      ...prev,
      keywords: prev.keywords.filter(kw => kw !== keywordToDelete)
    }));
  };

  const handleClear = () => {
    setFormData({
      title: '',
      contentType: 'article',
      content: '',
      targetAudience: '',
      keywords: []
    });
    if (editorRef.current) {
      editorRef.current.innerHTML = '';
    }
    setCurrentKeyword('');
    setError(null);
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <GridLegacy container spacing={3}>
        <GridLegacy item xs={12}>
          <TextField
            fullWidth
            label="Title"
            variant="outlined"
            value={formData.title}
            onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
            required
          />
        </GridLegacy>

        <GridLegacy item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>Content Type</InputLabel>
            <Select
              value={formData.contentType}
              onChange={(e) => setFormData(prev => ({ ...prev, contentType: e.target.value }))}
              label="Content Type"
            >
              <MenuItem value="article">Article</MenuItem>
              <MenuItem value="blog_post">Blog Post</MenuItem>
              <MenuItem value="product_description">Product Description</MenuItem>
              <MenuItem value="social_media">Social Media</MenuItem>
              <MenuItem value="email">Email</MenuItem>
              <MenuItem value="landing_page">Landing Page</MenuItem>
            </Select>
          </FormControl>
        </GridLegacy>

        <GridLegacy item xs={12} md={6}>
          <TextField
            fullWidth
            label="Target Audience"
            variant="outlined"
            value={formData.targetAudience}
            onChange={(e) => setFormData(prev => ({ ...prev, targetAudience: e.target.value }))}
            placeholder="e.g., Tech professionals, Marketing teams"
          />
        </GridLegacy>

        <GridLegacy item xs={12}>
          <Typography variant="subtitle2" gutterBottom>
            Content Editor
          </Typography>
          <Paper variant="outlined">
            <EditorToolbar editorRef={editorRef} />
            <Box
              ref={editorRef}
              contentEditable
              sx={{
                minHeight: 300,
                p: 2,
                outline: 'none',
                '&:focus': {
                  backgroundColor: 'action.hover'
                },
                '& p': { margin: 0, marginBottom: 1 },
                '& h1, & h2, & h3': { marginTop: 2, marginBottom: 1 }
              }}
              onPaste={(e) => {
                e.preventDefault();
                const text = e.clipboardData.getData('text/plain');
                document.execCommand('insertText', false, text);
              }}
            />
          </Paper>
        </GridLegacy>

        <GridLegacy item xs={12}>
          <TextField
            fullWidth
            label="Keywords (press Enter to add)"
            variant="outlined"
            value={currentKeyword}
            onChange={(e) => setCurrentKeyword(e.target.value)}
            onKeyDown={handleAddKeyword}
            placeholder="SEO, optimization, content"
          />
          <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {formData.keywords.map((keyword) => (
              <Chip
                key={keyword}
                label={keyword}
                onDelete={() => handleDeleteKeyword(keyword)}
                size="small"
              />
            ))}
          </Box>
        </GridLegacy>

        {error && (
          <GridLegacy item xs={12}>
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          </GridLegacy>
        )}

        {isSuccess && (
          <GridLegacy item xs={12}>
            <Alert severity="success">
              Content submitted successfully! It will be processed for optimization.
            </Alert>
          </GridLegacy>
        )}

        <GridLegacy item xs={12}>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
            <Button
              variant="outlined"
              onClick={handleClear}
              startIcon={<ClearIcon />}
            >
              Clear
            </Button>
            <Button
              variant="outlined"
              onClick={() => setShowPreview(!showPreview)}
              startIcon={<PreviewIcon />}
            >
              {showPreview ? 'Hide Preview' : 'Preview'}
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={isLoading || !formData.title || !formData.content}
              startIcon={isLoading ? <CircularProgress size={20} /> : <SendIcon />}
            >
              {isLoading ? 'Submitting...' : 'Submit Content'}
            </Button>
          </Box>
        </GridLegacy>

        {showPreview && (
          <GridLegacy item xs={12}>
            <ContentPreview
              title={formData.title}
              content={formData.content}
              contentType={formData.contentType}
              keywords={formData.keywords}
              targetAudience={formData.targetAudience}
            />
          </GridLegacy>
        )}
      </GridLegacy>
    </Box>
  );
}