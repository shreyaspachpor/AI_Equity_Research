import React, { useState } from 'react';
import { Upload, FileCheck, RefreshCw, Download, AlertCircle } from 'lucide-react';
import './index.css';

const API_BASE = 'http://localhost:8000';
const OPENROUTER_MODEL = 'gpt-4o';

export default function App() {
  const [reportName, setReportName] = useState('');
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);
  
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

    try {
      const formData = new FormData();
      formData.append('company_name', reportName);
      formData.append('model', OPENROUTER_MODEL);
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
  };

  return (
    <div className="container">
      <div className="solid-card">
        {!report ? (
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
        ) : (
          <div className="success-container">
            <div className="success-circle">
              <FileCheck size={40} />
            </div>
            <h2 className="title">Ready</h2>
            
            <a
              href={`${API_BASE}${report.download_url}`}
              target="_blank"
              rel="noreferrer"
              className="download-btn"
            >
              <Download size={20} />
              <span>Download PDF</span>
            </a>
            
            <button className="reset-btn" onClick={handleReset}>
              Start Over
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
