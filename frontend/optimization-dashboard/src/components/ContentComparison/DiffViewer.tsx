import React, { useMemo } from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import { DiffChange } from '../../types';

interface DiffViewerProps {
  original: string;
  optimized: string;
  changes: DiffChange[];
  viewMode: 'split' | 'unified';
}

const DiffViewer: React.FC<DiffViewerProps> = ({ original, optimized, changes, viewMode }) => {
  const theme = useTheme();

  const renderUnifiedView = () => {
    return (
      <Box
        sx={{
          height: '100%',
          overflow: 'auto',
          bgcolor: theme.palette.mode === 'dark' ? 'grey.900' : 'grey.50',
          borderRadius: 1,
          p: 2,
          fontFamily: 'monospace',
          fontSize: '0.875rem',
          lineHeight: 1.6,
        }}
      >
        {changes.map((change, index) => {
          const bgColor = change.type === 'add'
            ? theme.palette.success.light + '30'
            : change.type === 'remove'
            ? theme.palette.error.light + '30'
            : 'transparent';

          const textDecoration = change.type === 'remove' ? 'line-through' : 'none';
          const opacity = change.type === 'remove' ? 0.6 : 1;

          return (
            <Box
              key={index}
              component="span"
              sx={{
                backgroundColor: bgColor,
                textDecoration,
                opacity,
                borderRadius: change.type !== 'equal' ? '2px' : 0,
                padding: change.type !== 'equal' ? '0 2px' : 0,
              }}
            >
              {change.value}
            </Box>
          );
        })}
      </Box>
    );
  };

  const renderSplitView = () => {
    // Split changes into lines for side-by-side view
    const originalLines = original.split('\n');
    const optimizedLines = optimized.split('\n');

    return (
      <Box sx={{ display: 'flex', height: '100%', gap: 2 }}>
        {/* Original Content */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
            Original
          </Typography>
          <Box
            sx={{
              flex: 1,
              overflow: 'auto',
              bgcolor: theme.palette.mode === 'dark' ? 'grey.900' : 'grey.50',
              borderRadius: 1,
              p: 2,
              border: 1,
              borderColor: 'divider',
            }}
          >
            <SyntaxHighlighter
              language="markdown"
              style={atomOneDark}
              showLineNumbers
              customStyle={{
                margin: 0,
                background: 'transparent',
                fontSize: '0.875rem',
              }}
            >
              {original}
            </SyntaxHighlighter>
          </Box>
        </Box>

        {/* Optimized Content */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold', color: 'primary.main' }}>
            Optimized
          </Typography>
          <Box
            sx={{
              flex: 1,
              overflow: 'auto',
              bgcolor: theme.palette.mode === 'dark' ? 'grey.900' : 'grey.50',
              borderRadius: 1,
              p: 2,
              border: 1,
              borderColor: 'primary.main',
            }}
          >
            <SyntaxHighlighter
              language="markdown"
              style={atomOneDark}
              showLineNumbers
              customStyle={{
                margin: 0,
                background: 'transparent',
                fontSize: '0.875rem',
              }}
            >
              {optimized}
            </SyntaxHighlighter>
          </Box>
        </Box>
      </Box>
    );
  };

  return viewMode === 'unified' ? renderUnifiedView() : renderSplitView();
};

export default DiffViewer;