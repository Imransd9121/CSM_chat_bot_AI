import React, { useState } from 'react';
import { FileText, ExternalLink, Loader2, CheckCircle, Trash2 } from 'lucide-react';
import { Document } from '../../types';

interface DocumentListProps {
  documents: Document[];
  processingDocuments: Set<string>;
  onSelectDocument: (document: Document) => void;
  onDeleteDocument: (docId: string) => Promise<void> | void;
  selectedDocumentId?: string;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  processingDocuments,
  onSelectDocument,
  onDeleteDocument,
  selectedDocumentId
}) => {
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);

  const handleDelete = async (doc: Document) => {
    await onDeleteDocument(doc.id);
    setDeleteMessage(`Successfully deleted "${doc.name}"`);
    setTimeout(() => setDeleteMessage(null), 3000);
  };

  if (documents.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center transition-colors duration-200">
        <FileText className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
        <p className="text-gray-600 dark:text-gray-400 mb-2">No documents uploaded yet</p>
        <p className="text-sm text-gray-500 dark:text-gray-500">Upload a document to start asking questions</p>
        {deleteMessage && (
          <div className="mt-4 text-green-600 dark:text-green-400 text-sm">{deleteMessage}</div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 transition-colors duration-200">
      <div className="p-6 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Your Documents</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Select a document to start chatting</p>
        {deleteMessage && (
          <div className="mt-2 text-green-600 dark:text-green-400 text-sm">{deleteMessage}</div>
        )}
      </div>
      
      <div className="p-4 space-y-3">
        {documents.map((document) => {
          const isProcessing = processingDocuments.has(document.id);
          const isSelected = selectedDocumentId === document.id;
          
          return (
            <div
              key={document.id}
              className={`p-4 rounded-lg border transition-all duration-200 cursor-pointer ${
                isSelected
                  ? 'border-blue-200 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20'
                  : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
              onClick={() => document.processed && onSelectDocument(document)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  <div className="flex-shrink-0">
                    {document.type === 'url' ? (
                      <ExternalLink className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                    ) : (
                      <FileText className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                    )}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {document.name}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-500">
                      Uploaded {new Date(document.uploadedAt).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  {isProcessing ? (
                    <div className="flex items-center space-x-2 text-amber-600 dark:text-amber-400">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="text-xs">Processing...</span>
                    </div>
                  ) : document.processed ? (
                    <div className="flex items-center space-x-2 text-green-600 dark:text-green-400">
                      <CheckCircle className="w-4 h-4" />
                      <span className="text-xs">Ready</span>
                    </div>
                  ) : (
                    <div className="text-xs text-gray-500 dark:text-gray-500">Processing...</div>
                  )}
                  
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(document);
                    }}
                    className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors duration-200"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              
              {document.url && (
                <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                  <p className="text-xs text-gray-500 dark:text-gray-500 truncate">
                    Source: {document.url}
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};