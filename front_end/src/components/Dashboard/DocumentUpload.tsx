import React, { useState, useRef } from 'react';
import { Upload, FileText, Link, Loader2 } from 'lucide-react';
import { Document } from '../../types';

interface DocumentUploadProps {
  onFileUpload: (file: File) => Promise<Document>;
  onUrlUpload: (url: string, name: string) => Promise<Document>;
  processingDocuments: Set<string>;
}

export const DocumentUpload: React.FC<DocumentUploadProps> = ({
  onFileUpload,
  onUrlUpload,
  processingDocuments
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [uploadMethod, setUploadMethod] = useState<'file' | 'url'>('file');
  const [url, setUrl] = useState('');
  const [fileName, setFileName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileUpload = async (file: File) => {
    if (!file.type.includes('pdf') && !file.type.includes('doc')) {
      setError('Please upload a PDF or DOC file');
      return;
    }

    setLoading(true);
    setError('');
    setSuccessMessage('');
    try {
      const doc = await onFileUpload(file);
      if (doc && (doc as any).message) {
        setSuccessMessage((doc as any).message);
      }
    } catch (error: any) {
      setError(error.message || 'Upload failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleUrlUpload = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setError('');
    setSuccessMessage('');
    try {
      const doc = await onUrlUpload(url, fileName || 'Document from URL');
      if (doc && (doc as any).message) {
        setSuccessMessage((doc as any).message);
      }
      setUrl('');
      setFileName('');
    } catch (error: any) {
      setError(error.message || 'URL upload failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 transition-colors duration-200">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Upload Document</h3>
      {successMessage && (
        <div className="mb-4 text-green-600 dark:text-green-400 text-sm">{successMessage}</div>
      )}
      {error && (
        <div className="mb-4 text-red-600 dark:text-red-400 text-sm">{error}</div>
      )}
      <div className="flex space-x-4 mb-6">
        <button
          onClick={() => setUploadMethod('file')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors duration-200 ${
            uploadMethod === 'file'
              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700'
              : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-600'
          }`}
        >
          <Upload className="w-4 h-4" />
          <span>Upload File</span>
        </button>
        <button
          onClick={() => setUploadMethod('url')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors duration-200 ${
            uploadMethod === 'url'
              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700'
              : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-600'
          }`}
        >
          <Link className="w-4 h-4" />
          <span>From URL</span>
        </button>
      </div>

      {uploadMethod === 'file' ? (
        <div
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors duration-200 ${
            dragActive
              ? 'border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-900/20'
              : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx"
            onChange={(e) => e.target.files && handleFileUpload(e.target.files[0])}
            className="hidden"
          />
          
          <FileText className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 mb-2">Drag and drop your document here</p>
          <p className="text-sm text-gray-500 dark:text-gray-500 mb-4">or</p>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-6 py-2 rounded-lg transition-colors duration-200 flex items-center space-x-2 mx-auto"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{loading ? 'Uploading...' : 'Choose File'}</span>
          </button>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">Supports PDF and DOC files</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Document URL
            </label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="https://example.com/document.pdf"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Document Name (Optional)
            </label>
            <input
              type="text"
              value={fileName}
              onChange={(e) => setFileName(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="My Document"
            />
          </div>
          <button
            onClick={handleUrlUpload}
            disabled={!url.trim() || loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-6 py-3 rounded-lg transition-colors duration-200 flex items-center justify-center space-x-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{loading ? 'Processing...' : 'Upload from URL'}</span>
          </button>
        </div>
      )}
    </div>
  );
};