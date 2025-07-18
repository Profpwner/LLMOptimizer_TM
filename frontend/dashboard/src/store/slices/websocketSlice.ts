import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export enum ConnectionStatus {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
}

interface WebSocketState {
  status: ConnectionStatus;
  error: string | null;
  reconnectAttempts: number;
  lastMessage: any | null;
  messageQueue: any[];
}

const initialState: WebSocketState = {
  status: ConnectionStatus.DISCONNECTED,
  error: null,
  reconnectAttempts: 0,
  lastMessage: null,
  messageQueue: [],
};

const websocketSlice = createSlice({
  name: 'websocket',
  initialState,
  reducers: {
    setConnectionStatus: (state, action: PayloadAction<ConnectionStatus>) => {
      state.status = action.payload;
      if (action.payload === ConnectionStatus.CONNECTED) {
        state.reconnectAttempts = 0;
        state.error = null;
      }
    },
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload;
      state.status = ConnectionStatus.ERROR;
    },
    incrementReconnectAttempts: (state) => {
      state.reconnectAttempts += 1;
    },
    resetReconnectAttempts: (state) => {
      state.reconnectAttempts = 0;
    },
    setLastMessage: (state, action: PayloadAction<any>) => {
      state.lastMessage = action.payload;
    },
    addToMessageQueue: (state, action: PayloadAction<any>) => {
      state.messageQueue.push(action.payload);
    },
    clearMessageQueue: (state) => {
      state.messageQueue = [];
    },
  },
});

export const {
  setConnectionStatus,
  setError,
  incrementReconnectAttempts,
  resetReconnectAttempts,
  setLastMessage,
  addToMessageQueue,
  clearMessageQueue,
} = websocketSlice.actions;

export default websocketSlice.reducer;