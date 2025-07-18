import React, { useState, useCallback, useMemo } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Container,
  Paper,
  SpeedDial,
  SpeedDialIcon,
  SpeedDialAction,
  useTheme,
  alpha,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Timeline as TimelineIcon,
  BubbleChart as BubbleChartIcon,
  ShowChart as ShowChartIcon,
  Settings as SettingsIcon,
  Brightness4 as DarkModeIcon,
  Brightness7 as LightModeIcon,
  Add as AddIcon,
  ThreeDRotation as ThreeDIcon,
  Psychology as PsychologyIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { useAppSelector, useAppDispatch } from '../hooks/redux';
import { setTheme, updateWidget, DashboardWidget } from '../store/slices/dashboardSlice';
import KPICard from './widgets/KPICard';
import TimeSeriesChart from './widgets/TimeSeriesChart';
import HeatmapWidget from './widgets/HeatmapWidget';
import FunnelChart from './widgets/FunnelChart';
import ComparisonWidget from './widgets/ComparisonWidget';
import Network3D from './widgets/Network3D';
import PredictionChart from './widgets/PredictionChart';
import ConnectionStatus from './ConnectionStatus';
import DateRangePicker from './DateRangePicker';
import ExportMenu from './ExportMenu';
import { useInitializeDashboard } from '../hooks/useInitializeDashboard';
import { ContentInputTabs } from './ContentInput';

const drawerWidth = 240;

const Dashboard: React.FC = () => {
  const dispatch = useAppDispatch();
  const theme = useTheme();
  const { currentLayout, fullscreenWidget } = useAppSelector((state) => state.dashboard);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [speedDialOpen, setSpeedDialOpen] = useState(false);
  const [currentView, setCurrentView] = useState<'dashboard' | 'content-input'>('dashboard');

  // Initialize dashboard with sample data
  useInitializeDashboard();

  const handleThemeToggle = () => {
    dispatch(setTheme(theme.palette.mode === 'light' ? 'dark' : 'light'));
  };

  const handleLayoutChange = useCallback(
    (layout: any[]) => {
      if (!currentLayout) return;

      const updatedWidgets = currentLayout.widgets.map((widget) => {
        const layoutItem = layout.find((item) => item.i === widget.id);
        if (layoutItem) {
          return {
            ...widget,
            x: layoutItem.x,
            y: layoutItem.y,
            w: layoutItem.w,
            h: layoutItem.h,
          };
        }
        return widget;
      });

      updatedWidgets.forEach((widget) => {
        dispatch(updateWidget(widget));
      });
    },
    [currentLayout, dispatch]
  );

  const renderWidget = useCallback((widget: DashboardWidget) => {
    const commonProps = {
      widgetId: widget.id,
      config: widget.config || {},
    };

    switch (widget.type) {
      case 'kpi':
        return <KPICard {...commonProps} />;
      case 'chart':
        return <TimeSeriesChart {...commonProps} />;
      case 'heatmap':
        return <HeatmapWidget {...commonProps} />;
      case 'funnel':
        return <FunnelChart {...commonProps} />;
      case 'comparison':
        return <ComparisonWidget {...commonProps} />;
      case '3d-network':
        return <Network3D {...commonProps} />;
      case 'prediction':
        return <PredictionChart {...commonProps} />;
      default:
        return <div>Unknown widget type</div>;
    }
  }, []);

  const layout = useMemo(() => {
    if (!currentLayout) return [];
    return currentLayout.widgets.map((widget) => ({
      i: widget.id,
      x: widget.x,
      y: widget.y,
      w: widget.w,
      h: widget.h,
      minW: widget.minW || 2,
      minH: widget.minH || 2,
      maxW: widget.maxW,
      maxH: widget.maxH,
    }));
  }, [currentLayout]);

  const speedDialActions = [
    { icon: <DashboardIcon />, name: 'KPI Card', type: 'kpi' },
    { icon: <TimelineIcon />, name: 'Time Series Chart', type: 'chart' },
    { icon: <BubbleChartIcon />, name: 'Heatmap', type: 'heatmap' },
    { icon: <ShowChartIcon />, name: 'Funnel Chart', type: 'funnel' },
    { icon: <ThreeDIcon />, name: '3D Network', type: '3d-network' },
    { icon: <PsychologyIcon />, name: 'Predictions', type: 'prediction' },
  ];

  const handleAddWidget = (type: string) => {
    // This would be implemented to add a new widget
    console.log('Add widget of type:', type);
    setSpeedDialOpen(false);
  };

  if (fullscreenWidget) {
    const widget = currentLayout?.widgets.find((w) => w.id === fullscreenWidget);
    if (widget) {
      return (
        <Box sx={{ width: '100vw', height: '100vh', overflow: 'hidden' }}>
          {renderWidget(widget)}
        </Box>
      );
    }
  }

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerOpen ? drawerWidth : 0}px)` },
          ml: { sm: `${drawerOpen ? drawerWidth : 0}px` },
          transition: theme.transitions.create(['margin', 'width'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={() => setDrawerOpen(!drawerOpen)}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            LLM Optimizer Analytics Dashboard
          </Typography>
          <ConnectionStatus />
          <DateRangePicker />
          <ExportMenu />
          <IconButton sx={{ ml: 1 }} onClick={handleThemeToggle} color="inherit">
            {theme.palette.mode === 'dark' ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
        </Toolbar>
      </AppBar>

      <Drawer
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
          },
        }}
        variant="persistent"
        anchor="left"
        open={drawerOpen}
      >
        <Toolbar />
        <Box sx={{ overflow: 'auto' }}>
          <List>
            <ListItemButton
              selected={currentView === 'dashboard'}
              onClick={() => setCurrentView('dashboard')}
            >
              <ListItemIcon>
                <DashboardIcon />
              </ListItemIcon>
              <ListItemText primary="Dashboard" />
            </ListItemButton>
            <ListItemButton
              selected={currentView === 'content-input'}
              onClick={() => setCurrentView('content-input')}
            >
              <ListItemIcon>
                <EditIcon />
              </ListItemIcon>
              <ListItemText primary="Content Input" />
            </ListItemButton>
            <ListItemButton>
              <ListItemIcon>
                <TimelineIcon />
              </ListItemIcon>
              <ListItemText primary="Analytics" />
            </ListItemButton>
            <ListItemButton>
              <ListItemIcon>
                <PsychologyIcon />
              </ListItemIcon>
              <ListItemText primary="Predictions" />
            </ListItemButton>
            <ListItemButton>
              <ListItemIcon>
                <SettingsIcon />
              </ListItemIcon>
              <ListItemText primary="Settings" />
            </ListItemButton>
          </List>
        </Box>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerOpen ? drawerWidth : 0}px)` },
          ml: { sm: `${drawerOpen ? drawerWidth : 0}px` },
          transition: theme.transitions.create(['margin', 'width'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
          backgroundColor: theme.palette.background.default,
          minHeight: '100vh',
        }}
      >
        <Toolbar />
        <Container maxWidth={false}>
          {currentView === 'content-input' ? (
            <ContentInputTabs />
          ) : (
            <>
              {currentLayout ? (
                <GridLayout
                  className="layout"
                  layout={layout}
                  cols={12}
                  rowHeight={80}
                  width={1200}
                  onLayoutChange={handleLayoutChange}
                  draggableHandle=".widget-header"
                  style={{
                    backgroundColor: alpha(theme.palette.background.paper, 0.5),
                    borderRadius: theme.shape.borderRadius,
                    padding: theme.spacing(2),
                  }}
                >
                  {currentLayout.widgets.map((widget) => (
                    <Paper
                      key={widget.id}
                      elevation={3}
                      sx={{
                        height: '100%',
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column',
                      }}
                    >
                      {renderWidget(widget)}
                    </Paper>
                  ))}
                </GridLayout>
              ) : (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '60vh',
                  }}
                >
                  <Typography variant="h5" color="textSecondary">
                    No dashboard layout configured. Add widgets to get started.
                  </Typography>
                </Box>
              )}
            </>
          )}
        </Container>
      </Box>

      <SpeedDial
        ariaLabel="Add widget"
        sx={{ position: 'fixed', bottom: 32, right: 32 }}
        icon={<SpeedDialIcon openIcon={<AddIcon />} />}
        onClose={() => setSpeedDialOpen(false)}
        onOpen={() => setSpeedDialOpen(true)}
        open={speedDialOpen}
      >
        {speedDialActions.map((action) => (
          <SpeedDialAction
            key={action.name}
            icon={action.icon}
            tooltipTitle={action.name}
            onClick={() => handleAddWidget(action.type)}
          />
        ))}
      </SpeedDial>
    </Box>
  );
};

export default Dashboard;