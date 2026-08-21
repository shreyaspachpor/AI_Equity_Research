import React, { useState, useRef, useEffect } from 'react';
import { Upload, FileCheck, RefreshCw, Download, AlertCircle, MessageSquare, Edit3, Send, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import './index.css';

const API_BASE = 'http://localhost:8000';
const DEFAULT_MODEL = 'gpt-4o';

export default function App() {
  const [reportName, setReportName] = useState('');
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);
  
  // Chat State
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages]);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleGenerate = async () => {
    if (!file) {
      setError("Please upload a document.");
      return;
    }
    if (!reportName) {
      setError("Please enter a report name.");
      return;
    }

    setLoading(true);
    setError(null);
    setReport(null);
    setChatMessages([]);

    try {
      const formData = new FormData();
      formData.append('company_name', reportName);
      formData.append('model', DEFAULT_MODEL);
      formData.append('file', file);

      const res = await fetch(`${API_BASE}/api/generate`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || 'Failed to generate report');
      }

      setReport(data);
      // Initialize chat with a welcome message
      setChatMessages([{
        role: 'assistant',
        content: `Hello! I have generated the one-pager for ${data.data.company_name}. What would you like to know about it?`
      }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setReport(null);
    setFile(null);
    setReportName('');
    setChatMessages([]);
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || chatLoading || !report) return;
    
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);
    
    // Add empty assistant message that will be populated via SSE
    setChatMessages(prev => [...prev, { role: 'assistant', content: '', reasoning: '' }]);
    
    try {
      const res = await fetch(`${API_BASE}/api/chat/${report.report_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });
      
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || 'Failed to get response');
      }
      
      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6);
              if (!dataStr.trim()) continue;
              
              try {
                const data = JSON.parse(dataStr);
                
                setChatMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  
                  if (data.type === 'status') {
                     lastMessage.reasoning += `\n[System]: ${data.message}\n`;
                  } else if (data.type === 'chunk') {
                     if (data.content) lastMessage.content += data.content;
                     if (data.reasoning) lastMessage.reasoning += data.reasoning;
                  } else if (data.type === 'done') {
                     if (data.reply) lastMessage.content = data.reply;
                     if (data.reasoning) lastMessage.reasoning = data.reasoning;
                     
                     if (data.updated) {
                       // Trigger iframe refresh
                       setTimeout(() => setReport(r => ({ ...r, _ts: Date.now() })), 100);
                     }
                  } else if (data.type === 'error') {
                     lastMessage.content += `\nError: ${data.message}`;
                  }
                  
                  return newMessages;
                });
              } catch (e) {
                console.error("Error parsing SSE JSON:", e, dataStr);
              }
            }
          }
        }
      }
    } catch (err) {
      setChatMessages(prev => {
         const newMessages = [...prev];
         newMessages[newMessages.length - 1].content += `\nError: ${err.message}`;
         return newMessages;
      });
    } finally {
      setChatLoading(false);
    }
  };

  // Main UI
  if (!report) {
    return (
      <div className="container">
        <div className="solid-card">
          <div className="form-container">
            <h1 className="title">Research Generator</h1>
            
            <div className="input-group">
              <input
                type="text"
                placeholder="Enter Report Name"
                value={reportName}
                onChange={(e) => setReportName(e.target.value)}
                className="solid-input"
              />
            </div>

            <div
              className={`upload-zone ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => document.getElementById('fileInput').click()}
            >
              <input
                id="fileInput"
                type="file"
                accept=".pdf,.csv,.txt"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              
              {file ? (
                <div className="file-success">
                  <FileCheck size={32} className="success-icon" />
                  <span className="file-name">{file.name}</span>
                </div>
              ) : (
                <div className="upload-prompt">
                  <Upload size={32} className="upload-icon" />
                  <p>Upload Document</p>
                </div>
              )}
            </div>

            {error && (
              <div className="error-message">
                <AlertCircle size={18} />
                <span>{error}</span>
              </div>
            )}

            <button 
              className={`generate-btn ${loading ? 'loading' : ''}`}
              onClick={handleGenerate}
              disabled={loading || !file || !reportName}
            >
              {loading ? (
                <>
                  <RefreshCw className="spin" size={20} />
                  <span>Generating...</span>
                </>
              ) : (
                <span>Generate Report</span>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Dual-Pane Workspace UI
  return (
    <div className="workspace-container">
      {/* LEFT PANE: PDF Viewer */}
      <div className="pdf-pane">
        <div className="pdf-header">
          <h2>{report.data.company_name} - One Pager</h2>
          <div className="pdf-actions">
             <a href={`${API_BASE}${report.download_url}`} target="_blank" rel="noreferrer" className="action-btn">
               <Download size={18} />
               <span>Download</span>
             </a>
             <button className="action-btn outline" onClick={handleReset}>
               <RefreshCw size={18} />
               <span>Start Over</span>
             </button>
          </div>
        </div>
        {/* We append a timestamp to force the iframe to reload if the PDF updates */}
        <iframe 
          src={`${API_BASE}${report.download_url}#toolbar=0&view=FitH&t=${report._ts || Date.now()}`}
          key={report._ts || 'initial'}
          title="Generated Report"
          className="pdf-iframe"
        />
      </div>

      {/* RIGHT PANE: Unified Chat & Updates */}
      <div className="sidebar-pane">
        
        <div className="tab-content chat-content">
          <div className="chat-messages">
            {chatMessages.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                <div className="message-bubble">
                  {msg.reasoning && (
                    <div className="reasoning-box">
                      <details>
                        <summary>Model Reasoning</summary>
                        <ReactMarkdown>{msg.reasoning}</ReactMarkdown>
                      </details>
                    </div>
                  )}
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="chat-message assistant">
                <div className="message-bubble typing">
                  <span className="dot"></span><span className="dot"></span><span className="dot"></span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          
          <div className="chat-input-area">
            <input 
              type="text" 
              placeholder="Ask a question or propose an update..." 
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSendMessage()}
            />
            <button onClick={handleSendMessage} disabled={chatLoading || !chatInput.trim()}>
              <Send size={18} />
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
