import React from 'react';
import { Chip, Tooltip } from '@mui/material';
import {
  WifiOff as DisconnectedIcon,
  Wifi as ConnectedIcon,
  WifiTethering as ConnectingIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { useAppSelector } from '../hooks/redux';
import { ConnectionStatus as Status } from '../store/slices/websocketSlice';

const ConnectionStatus: React.FC = () => {
  const { status, error, reconnectAttempts } = useAppSelector((state) => state.websocket);

  const getStatusConfig = () => {
    switch (status) {
      case Status.CONNECTED:
        return {
          label: 'Connected',
          color: 'success' as const,
          icon: <ConnectedIcon />,
        };
      case Status.CONNECTING:
        return {
          label: `Connecting${reconnectAttempts > 0 ? ` (${reconnectAttempts})` : ''}`,
          color: 'warning' as const,
          icon: <ConnectingIcon />,
        };
      case Status.DISCONNECTED:
        return {
          label: 'Disconnected',
          color: 'default' as const,
          icon: <DisconnectedIcon />,
        };
      case Status.ERROR:
        return {
          label: 'Error',
          color: 'error' as const,
          icon: <ErrorIcon />,
        };
      default:
        return {
          label: 'Unknown',
          color: 'default' as const,
          icon: <DisconnectedIcon />,
        };
    }
  };

  const config = getStatusConfig();

  return (
    <Tooltip title={error || `WebSocket ${config.label.toLowerCase()}`}>
      <Chip
        icon={config.icon}
        label={config.label}
        color={config.color}
        size="small"
        sx={{ mr: 2 }}
      />
    </Tooltip>
  );
};

export default ConnectionStatus;