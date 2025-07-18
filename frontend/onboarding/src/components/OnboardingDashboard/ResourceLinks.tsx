import React from 'react';
import {
  Paper,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Box,
  Chip,
} from '@mui/material';
import ArticleIcon from '@mui/icons-material/Article';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
import ForumIcon from '@mui/icons-material/Forum';
import LiveHelpIcon from '@mui/icons-material/LiveHelp';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import { motion } from 'framer-motion';

const resources = [
  {
    id: 'knowledge-base',
    title: 'Knowledge Base',
    description: 'Comprehensive guides and tutorials',
    icon: <MenuBookIcon />,
    url: '/help/knowledge-base',
    badge: '50+ articles',
  },
  {
    id: 'video-tutorials',
    title: 'Video Tutorials',
    description: 'Watch and learn at your own pace',
    icon: <VideoLibraryIcon />,
    url: '/help/videos',
    badge: 'New',
  },
  {
    id: 'community-forum',
    title: 'Community Forum',
    description: 'Connect with other users',
    icon: <ForumIcon />,
    url: '/community',
    badge: 'Active',
  },
  {
    id: 'support',
    title: 'Live Support',
    description: '24/7 chat support available',
    icon: <LiveHelpIcon />,
    url: '/support',
    badge: 'Online',
  },
  {
    id: 'documentation',
    title: 'API Documentation',
    description: 'For developers and integrations',
    icon: <ArticleIcon />,
    url: '/docs/api',
    badge: null,
  },
];

export const ResourceLinks: React.FC = () => {
  const handleResourceClick = (url: string) => {
    // In a real app, this would navigate to the resource
    console.log('Navigate to:', url);
  };

  return (
    <Paper sx={{ p: 3, height: '100%' }} className="help-center">
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h6">Learning Resources</Typography>
        <Chip label="Help" size="small" color="info" />
      </Box>
      <List>
        {resources.map((resource, index) => (
          <motion.div
            key={resource.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <ListItem disablePadding>
              <ListItemButton onClick={() => handleResourceClick(resource.url)}>
                <ListItemIcon>{resource.icon}</ListItemIcon>
                <ListItemText
                  primary={resource.title}
                  secondary={resource.description}
                />
                {resource.badge && (
                  <Chip
                    label={resource.badge}
                    size="small"
                    color={resource.badge === 'Online' ? 'success' : 'default'}
                    variant={resource.badge === 'New' ? 'filled' : 'outlined'}
                  />
                )}
              </ListItemButton>
            </ListItem>
          </motion.div>
        ))}
      </List>
    </Paper>
  );
};