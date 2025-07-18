import React from 'react';
import {
  Paper,
  Typography,
  Box,
  Chip,
  Divider
} from '@mui/material';

interface ContentPreviewProps {
  title: string;
  content: string;
  contentType: string;
  keywords: string[];
  targetAudience?: string;
}

export default function ContentPreview({
  title,
  content,
  contentType,
  keywords,
  targetAudience
}: ContentPreviewProps) {
  // Function to safely render HTML content
  const createMarkup = (html: string) => {
    return { __html: html };
  };

  const formatContentType = (type: string) => {
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <Paper variant="outlined" sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Content Preview
      </Typography>
      <Divider sx={{ mb: 2 }} />

      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Title
        </Typography>
        <Typography variant="h5" gutterBottom>
          {title || 'Untitled'}
        </Typography>
      </Box>

      <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Content Type
          </Typography>
          <Chip label={formatContentType(contentType)} size="small" />
        </Box>

        {targetAudience && (
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Target Audience
            </Typography>
            <Typography variant="body2">
              {targetAudience}
            </Typography>
          </Box>
        )}
      </Box>

      {keywords.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Keywords
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {keywords.map((keyword) => (
              <Chip
                key={keyword}
                label={keyword}
                size="small"
                variant="outlined"
              />
            ))}
          </Box>
        </Box>
      )}

      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Content
        </Typography>
        <Paper
          variant="outlined"
          sx={{
            p: 2,
            backgroundColor: 'grey.50',
            maxHeight: 400,
            overflow: 'auto',
            '& h1': { fontSize: '2em', marginTop: 0 },
            '& h2': { fontSize: '1.5em' },
            '& h3': { fontSize: '1.17em' },
            '& p': { marginBottom: '1em' },
            '& ul, & ol': { marginLeft: '2em' }
          }}
        >
          <div 
            dangerouslySetInnerHTML={createMarkup(content || '<p>No content provided</p>')}
          />
        </Paper>
      </Box>

      <Typography variant="caption" color="text.secondary">
        This is a preview of how your content will be stored. The actual optimization
        will be performed after submission.
      </Typography>
    </Paper>
  );
}