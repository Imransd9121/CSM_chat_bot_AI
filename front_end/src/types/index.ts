export interface User {
  id: string;
  name: string;
  email: string;
  createdAt: string;
}

export interface Document {
  id: string;
  name: string;
  type: 'pdf' | 'doc' | 'url';
  url?: string;
  content: string;
  uploadedAt: string;
  processed: boolean;
  message?: string;
}

export interface Message {
  id: string;
  type: 'user' | 'bot';
  content: string;
  timestamp: string;
  documentId?: string;
}

export interface ChatSession {
  id: string;
  userId: string;
  documentId: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

export interface ThemeContextType {
  isDark: boolean;
  toggleTheme: () => void;
}