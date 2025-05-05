# agent-react-hook

A React hook for interacting with agent APIs, supporting streaming responses, API key authentication, and easy integration with state management.

## Installation

```sh
npm install agent-react-hook
```

## Features

- 🔄 **Streaming Responses**: Real-time token updates as the agent generates them
- 🧠 **Node Updates**: Track internal states of agent nodes
- 🔑 **API Key Authentication**: Secure communication with your agent API
- 🧵 **Thread Management**: Continue conversations with thread IDs
- 🔌 **Event Callbacks**: Hooks for tokens, messages, errors, and more
- 🛑 **Abort Control**: Easily cancel requests in progress

## Usage

### Basic Example

```jsx
import React, { useState } from 'react';
import useAgent from 'agent-react-hook';

function ChatComponent() {
  const [inputValue, setInputValue] = useState('');
  
  const {
    messages,
    currentTokens,
    isLoading,
    error,
    submit
  } = useAgent({
    baseUrl: 'https://your-agent-api.com',
    apiKey: 'your-api-key' // Optional
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputValue.trim() && !isLoading) {
      submit(inputValue);
      setInputValue('');
    }
  };

  return (
    <div>
      <div>
        {messages.map((msg, idx) => (
          <div key={idx}>
            <strong>{msg.type}:</strong> {msg.content}
          </div>
        ))}
        
        {isLoading && currentTokens && (
          <div>
            <strong>AI (typing):</strong> {currentTokens}
          </div>
        )}
      </div>
      
      {error && <div style={{color: 'red'}}>{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Type a message..."
          disabled={isLoading}
        />
        <button type="submit" disabled={!inputValue.trim() || isLoading}>
          Send
        </button>
      </form>
    </div>
  );
}
```

### Advanced Example with All Options

```jsx
import React, { useState, useEffect } from 'react';
import useAgent from 'agent-react-hook';

function AdvancedChatComponent() {
  const [inputValue, setInputValue] = useState('');
  const [threadId, setThreadId] = useState(null);
  const [userId, setUserId] = useState('user_123');
  
  // Initialize the agent hook with all available options
  const {
    messages,
    currentTokens,
    nodeUpdates,
    isLoading,
    threadId: hookThreadId,
    error,
    submit,
    stop,
    reset
  } = useAgent({
    baseUrl: 'https://your-agent-api.com',
    agentId: 'default',
    threadId: threadId,
    userId: userId,
    sessionId: 'session_123',
    model: 'gpt-4',
    apiKey: 'your-api-key',
    streamTokens: true,
    streamNodeUpdates: true,
    agentConfig: {
      temperature: 0.7,
      max_tokens: 2000
    },
    onToken: (token) => console.log('Token received:', token),
    onMessage: (message) => console.log('Message received:', message),
    onNodeUpdate: (update) => console.log('Node update:', update),
    onError: (err) => console.log('Error occurred:', err),
    onFinish: () => console.log('Stream finished'),
    onThreadId: (id) => {
      console.log('Thread ID updated:', id);
      setThreadId(id);
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputValue.trim() && !isLoading) {
      submit(inputValue);
      setInputValue('');
    }
  };

  // Save the thread ID in local storage or URL for persistence
  useEffect(() => {
    if (hookThreadId) {
      localStorage.setItem('threadId', hookThreadId);
    }
  }, [hookThreadId]);

  return (
    <div>
      {/* Messages display */}
      <div>
        {messages.map((msg, idx) => (
          <div key={idx}>
            <strong>{msg.type}:</strong> {msg.content}
          </div>
        ))}
        
        {isLoading && currentTokens && (
          <div>
            <strong>AI (typing):</strong> {currentTokens}
          </div>
        )}
      </div>
      
      {/* Node updates display */}
      {Object.keys(nodeUpdates).length > 0 && (
        <div>
          <h3>Node Updates</h3>
          {Object.entries(nodeUpdates).map(([node, data]) => (
            <div key={node}>
              <h4>{node}</h4>
              <pre>{JSON.stringify(data, null, 2)}</pre>
            </div>
          ))}
        </div>
      )}
      
      {/* Error display */}
      {error && <div style={{color: 'red'}}>{error}</div>}
      
      {/* Control buttons */}
      <div>
        <button onClick={stop} disabled={!isLoading}>
          Stop Generation
        </button>
        <button onClick={reset}>
          Reset Conversation
        </button>
      </div>
      
      {/* Message input */}
      <form onSubmit={handleSubmit}>
        <input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Type a message..."
          disabled={isLoading}
        />
        <button type="submit" disabled={!inputValue.trim() || isLoading}>
          Send
        </button>
      </form>
      
      {/* Thread ID display */}
      {hookThreadId && (
        <div>
          <small>Thread ID: {hookThreadId}</small>
        </div>
      )}
    </div>
  );
}
```

## API Reference

### `useAgent(options)`

#### Options

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `baseUrl` | string | Yes | - | Base URL of the agent API |
| `agentId` | string | No | 'default' | ID of the agent to use |
| `threadId` | string | No | null | Thread ID for continuing a conversation |
| `userId` | string | No | null | User ID to associate with this conversation |
| `sessionId` | string | No | null | Session ID to associate with this conversation |
| `model` | string | No | null | Model to use for the agent |
| `apiKey` | string | No | null | API key for authentication |
| `streamTokens` | boolean | No | true | Whether to stream tokens from the LLM |
| `streamNodeUpdates` | boolean | No | true | Whether to stream node updates |
| `agentConfig` | object | No | {} | Additional configuration for the agent |
| `onToken` | function | No | null | Callback when a token is received |
| `onMessage` | function | No | null | Callback when a full message is received |
| `onNodeUpdate` | function | No | null | Callback when a node update is received |
| `onError` | function | No | null | Callback when an error occurs |
| `onFinish` | function | No | null | Callback when streaming is complete |
| `onThreadId` | function | No | null | Callback when a thread ID is created or changes |

#### Return Values

| Property | Type | Description |
|----------|------|-------------|
| `messages` | array | Array of message objects |
| `currentTokens` | string | Current streaming tokens |
| `nodeUpdates` | object | Map of node updates by node name |
| `isLoading` | boolean | Whether a request is in progress |
| `threadId` | string | Current thread ID |
| `error` | string | Error message if any |
| `submit` | function | Function to submit a message |
| `stop` | function | Function to stop the current request |
| `reset` | function | Function to reset the conversation |
| `setThreadId` | function | Function to manually update the thread ID |

### Message Object Structure

```js
{
  type: "human" | "ai",
  content: string,
  thread_id: string,
  run_id: string,
  tool_calls: array,
  tool_call_id: string,
  response_metadata: object,
  custom_data: object
}
```

## Server Requirements

This hook is designed to work with agent APIs that support:

- Server-Sent Events (SSE) for streaming
- JSON format for requests and responses
- Bearer token authentication (when using the `apiKey` option)

## Security Considerations

- The hook does not log sensitive information to the console
- API keys are only sent in the Authorization header
- No data is stored outside of the component's state

## License

MIT

## Author

Janardhan Balaji

## Contributing

Contributions are welcome! This is an experimental package designed to make agent APIs more accessible in React applications.