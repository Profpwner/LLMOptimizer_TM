import React from 'react';
import {
  Paper,
  Typography,
  Box,
  Grid,
  Tooltip,
  Badge,
  Avatar,
} from '@mui/material';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';
import StarIcon from '@mui/icons-material/Star';
import FlashOnIcon from '@mui/icons-material/FlashOn';
import SchoolIcon from '@mui/icons-material/School';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import LocalFireDepartmentIcon from '@mui/icons-material/LocalFireDepartment';
import { motion } from 'framer-motion';

const achievements = [
  {
    id: 'first_login',
    name: 'Welcome Aboard',
    description: 'Created your account',
    icon: <RocketLaunchIcon />,
    color: '#4caf50',
    unlocked: true,
    points: 10,
  },
  {
    id: 'profile_complete',
    name: 'Profile Pro',
    description: 'Completed your profile',
    icon: <StarIcon />,
    color: '#ff9800',
    unlocked: true,
    points: 20,
  },
  {
    id: 'first_optimization',
    name: 'First Steps',
    description: 'Optimized your first content',
    icon: <FlashOnIcon />,
    color: '#2196f3',
    unlocked: false,
    points: 30,
  },
  {
    id: 'tour_complete',
    name: 'Explorer',
    description: 'Completed the product tour',
    icon: <SchoolIcon />,
    color: '#9c27b0',
    unlocked: false,
    points: 15,
  },
  {
    id: 'streak_3',
    name: 'On Fire',
    description: '3-day usage streak',
    icon: <LocalFireDepartmentIcon />,
    color: '#f44336',
    unlocked: false,
    points: 25,
  },
  {
    id: 'master',
    name: 'Optimization Master',
    description: 'Unlock all features',
    icon: <EmojiEventsIcon />,
    color: '#ffd700',
    unlocked: false,
    points: 100,
  },
];

export const AchievementBadges: React.FC = () => {
  const unlockedCount = achievements.filter(a => a.unlocked).length;
  const totalPoints = achievements
    .filter(a => a.unlocked)
    .reduce((sum, a) => sum + a.points, 0);

  return (
    <Paper sx={{ p: 3, height: '100%' }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
        <Box display="flex" alignItems="center">
          <EmojiEventsIcon color="warning" sx={{ mr: 1 }} />
          <Typography variant="h6">Achievements</Typography>
        </Box>
        <Box textAlign="right">
          <Typography variant="body2" color="text.secondary">
            {unlockedCount}/{achievements.length} unlocked
          </Typography>
          <Typography variant="caption" color="primary">
            {totalPoints} points
          </Typography>
        </Box>
      </Box>

      <Grid container spacing={2}>
        {achievements.map((achievement, index) => (
          <Grid item xs={4} key={achievement.id}>
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: index * 0.1, type: 'spring' }}
            >
              <Tooltip
                title={
                  <Box>
                    <Typography variant="body2">{achievement.name}</Typography>
                    <Typography variant="caption">{achievement.description}</Typography>
                    <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                      {achievement.points} points
                    </Typography>
                  </Box>
                }
                arrow
              >
                <Badge
                  badgeContent={achievement.unlocked ? '✓' : ''}
                  color="success"
                  invisible={!achievement.unlocked}
                >
                  <Avatar
                    sx={{
                      width: 56,
                      height: 56,
                      bgcolor: achievement.unlocked ? achievement.color : 'grey.300',
                      opacity: achievement.unlocked ? 1 : 0.5,
                      cursor: 'pointer',
                      transition: 'all 0.3s',
                      '&:hover': {
                        transform: achievement.unlocked ? 'scale(1.1)' : 'scale(1)',
                      },
                    }}
                  >
                    {achievement.icon}
                  </Avatar>
                </Badge>
              </Tooltip>
            </motion.div>
          </Grid>
        ))}
      </Grid>

      {unlockedCount < achievements.length && (
        <Box mt={2} textAlign="center">
          <Typography variant="caption" color="text.secondary">
            Complete more tasks to unlock achievements!
          </Typography>
        </Box>
      )}
    </Paper>
  );
};