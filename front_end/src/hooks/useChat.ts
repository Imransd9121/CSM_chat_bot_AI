import { useState, useEffect } from 'react';
import { ChatSession, Message, Document } from '../types';

const API_URL = 'http://localhost:5000';

export const useChat = (userId: string, token?: string) => {
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [isTyping, setIsTyping] = useState(false);

  // Fetch chat history for a document
  const fetchChatHistory = async (document: Document) => {
    if (!token) return;
    const response = await fetch(`${API_URL}/chat?doc_id=${document.id}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (response.ok) {
      const chats = await response.json();
      const messages: Message[] = chats.map((chat: any) => ({
        id: chat._id,
        type: 'user', // We'll add bot messages below
        content: chat.question,
        timestamp: chat.timestamp,
        documentId: chat.doc_id
      })).flatMap((chat: any, idx: number, arr: any[]) => [
        chat,
        {
          id: arr[idx]._id + '-bot',
          type: 'bot',
          content: chats[idx].answer,
          timestamp: chats[idx].timestamp,
          documentId: chats[idx].doc_id
        }
      ]);
      const session: ChatSession = {
        id: document.id,
        userId,
        documentId: document.id,
        messages,
        createdAt: document.uploadedAt,
        updatedAt: new Date().toISOString()
      };
      setCurrentSession(session);
    }
  };

  const createSession = (document: Document): ChatSession => {
    fetchChatHistory(document);
    const session: ChatSession = {
      id: document.id,
      userId,
      documentId: document.id,
      messages: [],
      createdAt: document.uploadedAt,
      updatedAt: new Date().toISOString()
    };
    setCurrentSession(session);
    return session;
  };

  const sendMessage = async (content: string, document: Document) => {
    if (!currentSession || !token) return;
    setIsTyping(true);
    // Add user message
    const userMessage: Message = {
      id: Math.random().toString(36).substr(2, 9),
      type: 'user',
      content,
      timestamp: new Date().toISOString(),
      documentId: document.id
    };
    setCurrentSession((prev) => prev ? { ...prev, messages: [...prev.messages, userMessage] } : null);
    // Send to backend
    const response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ doc_id: document.id, question: content })
    });
    if (response.ok) {
      const data = await response.json();
      const botMessage: Message = {
        id: Math.random().toString(36).substr(2, 9),
        type: 'bot',
        content: data.answer,
        timestamp: new Date().toISOString(),
        documentId: document.id
      };
      setCurrentSession((prev) => prev ? { ...prev, messages: [...prev.messages, botMessage] } : null);
    }
    setIsTyping(false);
  };

  const selectSession = (sessionId: string) => {
    // Not needed with backend, but could refetch if needed
  };

  const deleteSession = (sessionId: string) => {
    setCurrentSession(null);
  };

  return {
    chatSessions: [], // Not used with backend
    currentSession,
    isTyping,
    createSession,
    sendMessage,
    selectSession,
    deleteSession
  };
};