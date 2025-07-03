import { useState, useEffect } from 'react';
import { Document } from '../types';

const API_URL = 'http://localhost:5000'; // Change if backend runs elsewhere

const SAMPLE_DOCUMENTS: Document[] = [
  {
    id: 'sample-1',
    name: 'Sample Company Policy.pdf',
    type: 'pdf',
    content: `Company Policy Document

    Our company is committed to providing excellent customer service. We have a 30-day return policy for all products. 

    Working Hours: Monday to Friday, 9 AM to 6 PM
    Customer Support: Available 24/7 via phone and email
    Return Policy: 30 days from purchase date
    Warranty: 1 year warranty on all electronics
    Shipping: Free shipping on orders over $50
    
    For technical support, please contact our IT department at support@company.com or call 1-800-SUPPORT.`,
    uploadedAt: new Date().toISOString(),
    processed: true
  }
];

export const useDocuments = (token?: string) => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [processingDocuments, setProcessingDocuments] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fetchDocuments = async () => {
      if (!token) {
        setDocuments([]);
        return;
      }
      const response = await fetch(`${API_URL}/documents`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const docs = await response.json();
        setDocuments(
          docs.map((doc: any) => ({
            id: doc._id,
            name: doc.name,
            type: doc.type,
            url: doc.url,
            content: doc.content || '',
            uploadedAt: doc.uploaded_at,
            processed: doc.processed,
          }))
        );
      } else {
        setDocuments([]);
      }
    };
    fetchDocuments();
  }, [token]);

  const uploadDocument = async (file: File): Promise<Document> => {
    if (!token) throw new Error('Not authenticated');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', file.type.includes('pdf') ? 'pdf' : 'doc');
    formData.append('name', file.name);

    const response = await fetch(`${API_URL}/upload`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to upload document');
    }
    const newDoc: Document = {
      id: data._id || Math.random().toString(36).substr(2, 9),
      name: data.name || file.name,
      type: data.type || (file.type.includes('pdf') ? 'pdf' : 'doc'),
      url: data.url,
      content: data.content || '',
      uploadedAt: data.uploaded_at || new Date().toISOString(),
      processed: data.processed ?? true,
    };
    setDocuments((docs) => [...docs, newDoc]);
    return { ...newDoc, message: data.message };
  };

  const uploadFromUrl = async (url: string, name: string): Promise<Document> => {
    if (!token) throw new Error('Not authenticated');
    const response = await fetch(`${API_URL}/upload`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ name, type: 'url', url }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to upload document from URL');
    }
    const newDoc: Document = {
      id: data._id || Math.random().toString(36).substr(2, 9),
      name: data.name || name || 'Document from URL',
      type: data.type || 'url',
      url: data.url || url,
      content: data.content || '',
      uploadedAt: data.uploaded_at || new Date().toISOString(),
      processed: data.processed ?? true,
    };
    setDocuments((docs) => [...docs, newDoc]);
    return { ...newDoc, message: data.message };
  };

  const deleteDocument = async (docId: string) => {
    if (!token) throw new Error('Not authenticated');
    const response = await fetch(`${API_URL}/documents/${docId}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (response.ok) {
      setDocuments((docs) => docs.filter(doc => doc.id !== docId));
    } else {
      throw new Error('Failed to delete document');
    }
  };

  const resetDocuments = () => setDocuments([]);

  return {
    documents,
    processingDocuments,
    uploadDocument,
    uploadFromUrl,
    deleteDocument,
    resetDocuments
  };
};