import React from 'react';
import {
  Card,
  CardContent,
  CardMedia,
  CardActions,
  Typography,
  Box,
  Chip,
  Button,
  Rating,
  Stack,
  Tooltip,
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import { motion } from 'framer-motion';
import { Template } from '../../types';

interface TemplateCardProps {
  template: Template;
  onClick: () => void;
  viewMode: 'grid' | 'list';
  isRecommended?: boolean;
}

export const TemplateCard: React.FC<TemplateCardProps> = ({
  template,
  onClick,
  viewMode,
  isRecommended = false,
}) => {
  const difficultyColors = {
    beginner: 'success',
    intermediate: 'warning',
    advanced: 'error',
  } as const;

  if (viewMode === 'list') {
    return (
      <motion.div
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
      >
        <Card
          sx={{
            display: 'flex',
            cursor: 'pointer',
            '&:hover': { boxShadow: 4 },
          }}
          onClick={onClick}
        >
          {template.thumbnail && (
            <CardMedia
              component="img"
              sx={{ width: 140, height: 140, objectFit: 'cover' }}
              image={template.thumbnail}
              alt={template.name}
            />
          )}
          <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
            <CardContent sx={{ flex: '1 0 auto' }}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                <Box flex={1}>
                  <Typography variant="h6" component="div" gutterBottom>
                    {template.name}
                    {isRecommended && (
                      <Chip
                        label="Recommended"
                        size="small"
                        color="primary"
                        sx={{ ml: 1 }}
                      />
                    )}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    {template.description}
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    <Chip
                      label={template.category}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={template.difficulty}
                      size="small"
                      color={difficultyColors[template.difficulty]}
                    />
                    {template.industry && (
                      <Chip
                        label={template.industry}
                        size="small"
                        variant="outlined"
                      />
                    )}
                  </Stack>
                </Box>
                <Box sx={{ ml: 2, textAlign: 'right' }}>
                  <Rating value={4.5} precision={0.5} size="small" readOnly />
                  <Box display="flex" alignItems="center" mt={1}>
                    <AccessTimeIcon fontSize="small" sx={{ mr: 0.5 }} />
                    <Typography variant="caption">{template.estimatedTime}</Typography>
                  </Box>
                </Box>
              </Box>
            </CardContent>
          </Box>
        </Card>
      </motion.div>
    );
  }

  return (
    <motion.div
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
    >
      <Card
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          cursor: 'pointer',
          position: 'relative',
          '&:hover': { boxShadow: 6 },
        }}
        onClick={onClick}
      >
        {isRecommended && (
          <Chip
            label="Recommended"
            size="small"
            color="primary"
            sx={{
              position: 'absolute',
              top: 10,
              right: 10,
              zIndex: 1,
            }}
          />
        )}
        
        {template.thumbnail && (
          <CardMedia
            component="img"
            height="140"
            image={template.thumbnail}
            alt={template.name}
            sx={{ objectFit: 'cover' }}
          />
        )}
        
        <CardContent sx={{ flexGrow: 1 }}>
          <Typography gutterBottom variant="h6" component="div">
            {template.name}
          </Typography>
          
          <Typography variant="body2" color="text.secondary" paragraph>
            {template.description}
          </Typography>
          
          <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
            <Chip
              label={template.category}
              size="small"
              variant="outlined"
            />
            <Chip
              label={template.difficulty}
              size="small"
              color={difficultyColors[template.difficulty]}
            />
          </Stack>
          
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Box display="flex" alignItems="center">
              <AccessTimeIcon fontSize="small" sx={{ mr: 0.5, color: 'text.secondary' }} />
              <Typography variant="caption" color="text.secondary">
                {template.estimatedTime}
              </Typography>
            </Box>
            
            <Tooltip title="Popularity score">
              <Box display="flex" alignItems="center">
                <TrendingUpIcon fontSize="small" sx={{ mr: 0.5, color: 'success.main' }} />
                <Typography variant="caption" color="success.main">
                  {template.popularity}%
                </Typography>
              </Box>
            </Tooltip>
          </Box>
        </CardContent>
        
        <CardActions>
          <Button size="small" fullWidth variant="contained">
            Use Template
          </Button>
        </CardActions>
      </Card>
    </motion.div>
  );
};