import React, { useState, useEffect, useRef } from 'react';
import useAgent from 'agent-react-hook';
import './App.css';

function App() {
  const [inputValue, setInputValue] = useState('');
  const [savedThreadId, setSavedThreadId] = useState(() => {
    return localStorage.getItem('threadId') || null;
  });
  const textareaRef = useRef(null);
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  
  // Initialize agent hook with your backend configuration
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
    baseUrl: 'http://localhost:8000',
    agentId: 'research-assistant',
    threadId: savedThreadId,
    streamTokens: true,
    apiKey: '123',
    streamNodeUpdates: true,
    onToken: (token) => console.log('New token:', token),
    onNodeUpdate: (update) => console.log('Node update:', update.node),
    onThreadId: (id) => {
      console.log('Thread ID updated:', id);
      localStorage.setItem('threadId', id);
      setSavedThreadId(id);
    }
  });

  // Save thread ID to local storage when it changes
  useEffect(() => {
    if (threadId) {
      localStorage.setItem('threadId', threadId);
      setSavedThreadId(threadId);
    }
  }, [threadId]);

  // Adjust textarea height automatically
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [inputValue]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentTokens]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputValue.trim() && !isLoading) {
      submit(inputValue);
      setInputValue('');
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleReset = () => {
    reset();
    localStorage.removeItem('threadId');
    setSavedThreadId(null);
  };

  // Handle Enter key to submit (Shift+Enter for new line)
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Toggle agent thinking process visibility
  const [showThinking, setShowThinking] = useState(false);
  
  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>LangGraph Chat</h2>
        </div>

        <button 
          className="new-chat-button"
          onClick={handleReset}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 4V20M4 12H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          New Chat
        </button>

        <div className="conversations">
          {threadId && (
            <div className="conversation-item active">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M8 12H8.01M12 12H12.01M16 12H16.01M21 12C21 16.418 16.97 20 12 20C10.5286 20 9.14178 19.7127 7.91518 19.1996L3 20L4.5 16.5C3.57 15.2541 3 13.6985 3 12C3 7.582 7.03 4 12 4C16.97 4 21 7.582 21 12Z" 
                  stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <span>Current Thread</span>
            </div>
          )}
        </div>

        <div className="sidebar-footer">
          <div className="thread-info">
            {threadId ? `Thread ID: ${threadId.substring(0, 8)}...` : 'No active thread'}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content">
        <div className="chat-container" ref={chatContainerRef}>
          {messages.length === 0 ? (
            <div className="welcome-screen">
              <h1>LangGraph Research Assistant</h1>
              <p>Ask me anything to help with your research.</p>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`message ${msg.type === 'human' ? 'user-message' : 'assistant-message'}`}
                >
                  <div className="avatar">
                    {msg.type === 'human' ? (
                      <div className="user-avatar">U</div>
                    ) : (
                      <div className="ai-avatar">AI</div>
                    )}
                  </div>
                  <div className="message-content">
                    <div className="message-author">{msg.type === 'human' ? 'You' : 'Assistant'}</div>
                    <div className="message-text">{msg.content}</div>
                  </div>
                </div>
              ))}
              
              {isLoading && currentTokens && (
                <div className="message assistant-message">
                  <div className="avatar">
                    <div className="ai-avatar">AI</div>
                  </div>
                  <div className="message-content">
                    <div className="message-author">Assistant</div>
                    <div className="message-text">
                      {currentTokens}
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="input-container">
          <form onSubmit={handleSubmit} className="input-form">
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message the LangGraph Assistant..."
              disabled={isLoading}
              className="chat-input"
              rows="1"
            />
            <button 
              type="submit" 
              disabled={!inputValue.trim() || isLoading}
              className="send-button"
              aria-label="Send message"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M22 2L11 13M22 2L15 22L11 13M11 13L2 9L22 2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </form>
          
          <div className="input-footer">
            <button 
              onClick={() => setShowThinking(!showThinking)} 
              className={`thinking-toggle ${showThinking ? 'active' : ''}`}
            >
              {showThinking ? 'Hide' : 'Show'} Agent Thinking Process
            </button>
            
            {isLoading && (
              <button 
                onClick={stop} 
                className="stop-button"
              >
                Stop Generating
              </button>
            )}
          </div>
        </div>
        
        {/* Error message */}
        {error && (
          <div className="error-container">
            <div className="error-message">{error}</div>
          </div>
        )}
      </main>

      {/* Agent thinking process panel - conditionally rendered */}
      {showThinking && Object.keys(nodeUpdates).length > 0 && (
        <aside className="thinking-panel">
          <div className="thinking-header">
            <h3>Agent Thinking Process</h3>
            <button onClick={() => setShowThinking(false)} className="close-button">×</button>
          </div>
          <div className="node-grid">
            {Object.entries(nodeUpdates).map(([node, data]) => (
              <div key={node} className="node-card">
                <h4 className="node-title">{node}</h4>
                <div className="node-content">
                  <pre>{JSON.stringify(data, null, 2)}</pre>
                </div>
              </div>
            ))}
          </div>
        </aside>
      )}
    </div>
  );
}

export default App;
