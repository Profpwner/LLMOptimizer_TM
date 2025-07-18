import { useEffect } from 'react';
import { useAppSelector } from './useAppSelector';
import websocketService from '../services/websocket';

export const useWebSocket = (contentId?: string) => {
  const { connected } = useAppSelector((state) => state.websocket);

  useEffect(() => {
    // Connect on mount
    websocketService.connect();

    // Subscribe to content if ID provided
    if (contentId && connected) {
      websocketService.subscribeToContent(contentId);
    }

    // Cleanup
    return () => {
      if (contentId && connected) {
        websocketService.unsubscribeFromContent(contentId);
      }
    };
  }, [contentId, connected]);

  return { connected, websocketService };
};