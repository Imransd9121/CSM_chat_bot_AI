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
    const response = await fetch(`${API_URL}/chat?doc_id=${document.id}&t=${Date.now()}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (response.ok) {
      const chats = await response.json();
      console.log('Fetched chats from backend:', chats);
      const messages: Message[] = chats.map((chat: any) => ({
        id: chat._id,
        type: 'user', // We'll add bot messages below
        content: chat.question,
        timestamp: chat.timestamp,
        documentId: chat.doc_id
      })).flatMap((chat: any, idx: number, arr: any[]) => [
        chat,
        {
          id: ((arr[idx]._id || `bot-${idx}`) + '-bot'),
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
      setCurrentSession({
        ...session,
        messages: [...session.messages], // force new array reference
      });
      console.log('setCurrentSession called with:', session);
      setTimeout(() => {
        console.log('After setCurrentSession, currentSession:', session);
      }, 0);
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
      await fetchChatHistory(document);
      console.log('After fetchChatHistory, currentSession:', currentSession);
    }
    setIsTyping(false);
  };

  const selectSession = (sessionId: string) => {
    // Not needed with backend, but could refetch if needed
  };

  const deleteSession = (sessionId: string) => {
    setCurrentSession(null);
  };

  const clearChat = () => {
    setCurrentSession(null);
    // Add any other chat-related state resets here if needed
  };

  return {
    chatSessions: [], // Not used with backend
    currentSession,
    isTyping,
    createSession,
    sendMessage,
    selectSession,
    deleteSession,
    clearChat,
  };
};