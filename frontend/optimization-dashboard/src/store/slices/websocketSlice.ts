import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface WebSocketState {
  connected: boolean;
  connectionId: string | null;
  reconnectAttempts: number;
  lastError: string | null;
  lastPing: number | null;
}

const initialState: WebSocketState = {
  connected: false,
  connectionId: null,
  reconnectAttempts: 0,
  lastError: null,
  lastPing: null,
};

const websocketSlice = createSlice({
  name: 'websocket',
  initialState,
  reducers: {
    connected: (state, action: PayloadAction<string>) => {
      state.connected = true;
      state.connectionId = action.payload;
      state.reconnectAttempts = 0;
      state.lastError = null;
    },
    disconnected: (state) => {
      state.connected = false;
      state.connectionId = null;
    },
    reconnectAttempt: (state) => {
      state.reconnectAttempts += 1;
    },
    error: (state, action: PayloadAction<string>) => {
      state.lastError = action.payload;
    },
    ping: (state) => {
      state.lastPing = Date.now();
    },
  },
});

export const {
  connected,
  disconnected,
  reconnectAttempt,
  error,
  ping,
} = websocketSlice.actions;

export default websocketSlice.reducer;