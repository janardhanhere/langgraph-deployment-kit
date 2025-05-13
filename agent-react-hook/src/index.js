import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * React hook for interacting with the agent API
 * 
 * @param {Object} options - Configuration options for the agent
 * @param {string} options.baseUrl - Base URL of the agent API
 * @param {string} [options.agentId] - ID of the agent to use
 * @param {string} [options.threadId] - Thread ID for continuing a conversation
 * @param {string} [options.userId] - User ID to associate with this conversation
 * @param {string} [options.sessionId] - Session ID to associate with this conversation
 * @param {string} [options.model] - Model to use for the agent
 * @param {string} [options.apiKey] - API key for authentication
 * @param {boolean} [options.streamTokens=true] - Whether to stream tokens from the LLM
 * @param {boolean} [options.streamNodeUpdates=true] - Whether to stream node updates
 * @param {Object} [options.agentConfig={}] - Additional configuration for the agent
 * @param {Function} [options.onToken] - Callback when a token is received
 * @param {Function} [options.onMessage] - Callback when a full message is received
 * @param {Function} [options.onNodeUpdate] - Callback when a node update is received
 * @param {Function} [options.onError] - Callback when an error occurs
 * @param {Function} [options.onFinish] - Callback when streaming is complete
 * @param {Function} [options.onThreadId] - Callback when a thread ID is created or changes
 * @returns {Object} Methods and state for interacting with the agent
 */
export function useAgent(options) {
  const {
    baseUrl,
    agentId,
    threadId: initialThreadId,
    userId,
    sessionId,
    model,
    apiKey,
    streamTokens = true,
    streamNodeUpdates = true,
    agentConfig = {},
    onToken,
    onMessage,
    onNodeUpdate,
    onError,
    onFinish,
    onThreadId
  } = options;

  // State variables
  const [messages, setMessages] = useState([]);
  const [currentTokens, setCurrentTokens] = useState('');
  const [nodeUpdates, setNodeUpdates] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState(initialThreadId || null);
  const [error, setError] = useState(null);

  // Refs
  const abortControllerRef = useRef(null);
  
  // Update threadId when initialThreadId changes (from parent component)
  useEffect(() => {
    if (initialThreadId && initialThreadId !== threadId) {
      setThreadId(initialThreadId);
      onThreadId?.(initialThreadId);
    }
  }, [initialThreadId, threadId, onThreadId]);

  /**
   * Parse an SSE line from the server
   */
  const parseStreamLine = useCallback((line) => {
    line = line.trim();
    if (line.startsWith("data: ")) {
      const data = line.substring(6); // Remove "data: " prefix
      if (data === "[DONE]") {
        return null;
      }
      
      try {
        const parsed = JSON.parse(data);
        return parsed;
      } catch (e) {
        onError?.(`Error parsing data from server: ${e}`);
        return null;
      }
    }
    return null;
  }, [onError]);

  /**
   * Handle an event from the server
   */
  const handleEvent = useCallback((event) => {
    if (!event) return;
    
    switch (event.type) {
      case "token":
        setCurrentTokens(prev => prev + event.content);
        onToken?.(event.content);
        break;
        
      case "message":
        const message = event.content;
        setMessages(prev => [...prev, message]);
        onMessage?.(message);
        
        // If this is the first message from the agent and includes a thread ID, save it
        if (message.thread_id && !threadId) {
          setThreadId(message.thread_id);
          onThreadId?.(message.thread_id);
        }
        break;
        
      case "node_update":
        setNodeUpdates(prev => ({
          ...prev,
          [event.content.node]: event.content
        }));
        onNodeUpdate?.(event.content);
        break;
        
      case "error":
        setError(event.content);
        onError?.(event.content);
        break;
        
      default:
        // Silently ignore unknown event types
        break;
    }
  }, [onToken, onMessage, onNodeUpdate, onError, onThreadId, threadId]);

  /**
   * Clean up resources
   */
  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
    onFinish?.();
  }, [onFinish]);
  /**
   * Submit a message to the agent
   */
  const submit = useCallback(async (message) => {
    // Clean up any existing request
    cleanup();
    
    // Reset state for new request
    setCurrentTokens("");
    setNodeUpdates({}); // Reset node updates for each new message
    setError(null);
    setIsLoading(true);
    
    // Add user message optimistically
    const userMessage = {
      type: "human",
      content: message,
      tool_calls: [],
      tool_call_id: null,
      run_id: null,
      thread_id: threadId, // Include thread_id in user messages for consistency
      response_metadata: {},
      custom_data: {}
    };
    
    setMessages(prev => [...prev, userMessage]);
    
    // Create abort controller for this request
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    
    try {
      // Prepare URL and request body
      // Ensure baseUrl doesn't end with a slash
      const normalizedBaseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
      const url = `${normalizedBaseUrl}/${agentId || 'default'}/stream`;
      
      // Always include thread_id if we have one, even if it's empty
      const body = {
        message,
        stream_tokens: streamTokens,
        stream_node_updates: streamNodeUpdates,
        thread_id: threadId || "",
        ...(userId && { user_id: userId }),
        ...(sessionId && { session_id: sessionId }),
        ...(model && { model }),
        ...(Object.keys(agentConfig).length > 0 && { agent_config: agentConfig })
      };
      
      // Prepare headers
      const headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
      };
      
      // Add API key to headers if provided
      if (apiKey) {
        headers["Authorization"] = `Bearer ${apiKey}`;
      }
      
      // Make the request
      const response = await fetch(url, {
        method: "POST",
        headers: headers,
        body: JSON.stringify(body),
        signal: abortController.signal,
        // Add these to make fetch more compatible with older servers and proxies
        mode: 'cors',
        credentials: 'same-origin',
        cache: 'no-cache',
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error ${response.status}: ${errorText}`);
      }
      
      // Process the response as a stream
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Response body is null");
      }
      
      const decoder = new TextDecoder();
      let buffer = "";
      
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          break;
        }
        
        // Add new chunk to buffer and find complete lines
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        
        // Process all complete lines except the last one
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          if (line) {
            const event = parseStreamLine(line);
            if (event === null) {
              // End of stream
              cleanup();
              return;
            } else if (event) {
              handleEvent(event);
            }
          }
        }
        
        // Keep the last (potentially incomplete) line in the buffer
        buffer = lines[lines.length - 1];
      }
      
      // Process any remaining data in the buffer
      if (buffer.trim()) {
        const event = parseStreamLine(buffer.trim());
        if (event) {
          handleEvent(event);
        }
      }
      
      cleanup();
    } catch (err) {
      if (err.name !== "AbortError") {
        setError(err.message);
        onError?.(err.message);
      }
      cleanup();
    }
  }, [
    baseUrl,
    agentId,
    threadId,
    userId,
    sessionId,
    model,
    apiKey,
    streamTokens,
    streamNodeUpdates,
    agentConfig,
    parseStreamLine,
    handleEvent,
    cleanup,
    onError
  ]);

  /**
   * Stop the current request
   */
  const stop = useCallback(() => {
    cleanup();
  }, [cleanup]);

  /**
   * Reset the conversation
   */
  const reset = useCallback(() => {
    cleanup();
    setMessages([]);
    setCurrentTokens("");
    setNodeUpdates({});
    setError(null);
    
    if (!initialThreadId) {
      setThreadId(null);
    }
  }, [cleanup, initialThreadId]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    messages,
    currentTokens,
    nodeUpdates,
    isLoading,
    threadId,
    error,
    submit,
    stop,
    reset,
    // Add a specific method to update the thread ID manually
    setThreadId: (newThreadId) => {
      setThreadId(newThreadId);
      onThreadId?.(newThreadId);
    }
  };
}

// Export as default for easier importing
export default useAgent;