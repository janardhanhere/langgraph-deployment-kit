# LangGraph Deployment Kit

Author: Janardhan Balaji

This project provides a robust framework for deploying and running LangGraph agents as backend services, with seamless integration for React frontends using the `agent-react-hook` package. It also supports Langfuse integration for observability and analytics.

---

## Features
- **Plug-and-play LangGraph agents**: Easily add and deploy your own agents.
- **Streaming API**: Real-time responses for chat and agent applications.
- **React integration**: Use the published `agent-react-hook` npm package for frontend apps.
- **Langfuse analytics**: Optional observability and analytics with Langfuse.

---

## Requirements
- Python 3.10+
- Node.js (for React frontend)
- (Optional) Langfuse account for analytics

---

## 1. Add Your LangGraph Agent
- Place your custom LangGraph agent code in the `src/agents` directory.
- Import and register your agent in `src/agents/agents.py`:
  ```python
  from agents.my_agent import my_agent
  agents = {
      ... # existing agents
      "my-agent": Agent(description="My custom agent", graph=my_agent)
  }
  ```
- Set the agent name (key) you want to use as the default, or reference it in your React app via the `agentId` option.

---

## 2. Configure Langfuse (Optional, for Analytics)
- Add your Langfuse credentials to a `.env` file in the root directory:
  ```env
  LANGFUSE_PUBLIC_KEY=your_public_key
  LANGFUSE_SECRET_KEY=your_secret_key
  LANGFUSE_HOST=https://cloud.langfuse.com
  ```
- You can get these values from your Langfuse dashboard.

---

## 3. Run the Backend Service
- Start the backend service:
  ```sh
  python src/run_service.py
  ```

---

## 4. Integrate with React Frontend
- In your React project, install the hook:
  ```sh
  npm install agent-react-hook
  ```
- Use the `useAgent` hook in your React app. You can configure it with a wide range of options:

### All useAgent Options
| Option             | Type      | Required | Description                                                                                 |
|--------------------|-----------|----------|---------------------------------------------------------------------------------------------|
| baseUrl            | string    | Yes      | The base URL of your agent backend (e.g., http://localhost:8000).                           |
| agentId            | string    | No       | The agent name as registered in your backend (default: "default").                          |
| threadId           | string    | No       | Thread ID for continuing a conversation.                                                    |
| userId             | string    | No       | User ID to associate with this conversation.                                                |
| sessionId          | string    | No       | Session ID to associate with this conversation.                                             |
| apiKey             | string    | No       | API key for authentication (sent as Bearer token).                                          |
| streamTokens       | boolean   | No       | Whether to stream tokens from the LLM (default: true).                                      |
| streamNodeUpdates  | boolean   | No       | Whether to stream node updates (default: true).                                             |
| agentConfig        | object    | No       | Additional configuration for the agent (e.g., temperature, max_tokens, etc).                |
| onToken            | function  | No       | Callback when a token is received.                                                          |
| onMessage          | function  | No       | Callback when a full message is received.                                                   |
| onNodeUpdate       | function  | No       | Callback when a node update is received.                                                    |
| onError            | function  | No       | Callback when an error occurs.                                                              |
| onFinish           | function  | No       | Callback when streaming is complete.                                                        |
| onThreadId         | function  | No       | Callback when a thread ID is created or changes.                                            |

### Example Usage
```jsx
import React, { useState } from 'react';
import useAgent from 'agent-react-hook';

function ChatComponent() {
  const [inputValue, setInputValue] = useState('');
  const {
    messages,
    currentTokens,
    nodeUpdates,
    isLoading,
    threadId,
    error,
    submit,
    stop,
    reset,
    setThreadId
  } = useAgent({
    baseUrl: 'http://localhost:8000', // Your backend URL
    agentId: 'my-agent', // The agent name you registered
    threadId: 'your-thread-id',
    userId: 'user-123',
    sessionId: 'session-abc',
    apiKey: 'your-api-key',
    streamTokens: true,
    streamNodeUpdates: true,
    agentConfig: { temperature: 0.7, max_tokens: 2000 },
    onToken: (token) => console.log('Token:', token),
    onMessage: (msg) => console.log('Message:', msg),
    onNodeUpdate: (update) => console.log('Node update:', update),
    onError: (err) => console.error('Error:', err),
    onFinish: () => console.log('Stream finished'),
    onThreadId: (id) => console.log('Thread ID:', id)
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
      <button onClick={reset}>Reset</button>
      <button onClick={stop} disabled={!isLoading}>Stop</button>
      {threadId && <div>Thread ID: {threadId}</div>}
    </div>
  );
}
```

---

## Example Workflow
1. Add your agent code to `src/agents`.
2. Register it in `src/agents/agents.py`.
3. (Optional) Add Langfuse credentials to `.env`.
4. Start the backend with `python src/run_service.py`.
5. In your React app, use `agent-react-hook` to connect to your agent API.

---

## Notes
- The backend supports streaming responses and is designed for easy extension with new agents.
- The React hook (`agent-react-hook`) is published on npm for frontend integration.
- Langfuse integration is optional but recommended for observability.

---

## License
MIT
