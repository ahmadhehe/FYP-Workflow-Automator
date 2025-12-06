import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [events, setEvents] = useState([]);
  const [currentIteration, setCurrentIteration] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data === 'pong' || data.type === 'keepalive') {
          return;
        }

        setLastMessage(data);

        // Handle different event types
        switch (data.type) {
          case 'connected':
            setTaskStatus(data.data?.current_task ? 'running' : 'idle');
            break;
          
          case 'status':
            setTaskStatus(data.data?.status || 'unknown');
            break;
          
          case 'iteration':
            setCurrentIteration(data.data);
            break;
          
          case 'action':
            setEvents(prev => [...prev, {
              ...data.data,
              timestamp: data.timestamp,
              flow_id: data.flow_id
            }]);
            break;
          
          case 'complete':
            setTaskStatus('completed');
            setCurrentIteration(null);
            break;
          
          case 'error':
            setTaskStatus('error');
            break;
          
          case 'browser_started':
          case 'browser_stopped':
            // Handle browser state changes
            break;
          
          default:
            break;
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      
      // Attempt to reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
    }
  }, []);

  const clearEvents = useCallback(() => {
    setEvents([]);
    setCurrentIteration(null);
    setTaskStatus(null);
  }, []);

  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('ping');
    }
  }, []);

  useEffect(() => {
    connect();

    // Send periodic pings to keep connection alive
    const pingInterval = setInterval(sendPing, 25000);

    return () => {
      clearInterval(pingInterval);
      disconnect();
    };
  }, [connect, disconnect, sendPing]);

  return {
    isConnected,
    lastMessage,
    events,
    currentIteration,
    taskStatus,
    clearEvents,
    reconnect: connect,
  };
}

export default useWebSocket;
