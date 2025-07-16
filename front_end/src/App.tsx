import React, { useState, useEffect } from 'react';
import { useAuth } from './hooks/useAuth';
import { useDocuments } from './hooks/useDocuments';
import { useChat } from './hooks/useChat';
import { ThemeProvider } from './contexts/ThemeContext';
import { AuthLayout } from './components/Layout/AuthLayout';
import { Header } from './components/Layout/Header';
import { LoginForm } from './components/Auth/LoginForm';
import { RegisterForm } from './components/Auth/RegisterForm';
import { ForgotPassword } from './components/Auth/ForgotPassword';
import { DocumentUpload } from './components/Dashboard/DocumentUpload';
import { DocumentList } from './components/Dashboard/DocumentList';
import { ChatInterface } from './components/Chat/ChatInterface';
import { Document } from './types';
import { Routes, Route, Navigate } from 'react-router-dom';

function AppContent() {
  const { user, loading, login, register, logout } = useAuth();
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') || undefined : undefined;
  const { documents, processingDocuments, uploadDocument, uploadFromUrl, deleteDocument } = useDocuments(token);
  const chat = useChat(user?.id || '', token);
  
  const [authMode, setAuthMode] = useState<'login' | 'register' | 'forgot-password'>('login');
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [forceUpdate, setForceUpdate] = useState(0);

  useEffect(() => {
    // Clear chat state when user changes (login/logout)
    if (chat.clearChat) chat.clearChat();
  }, [user?.id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 dark:bg-gray-900 flex items-center justify-center transition-colors duration-200">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <AuthLayout>
        {authMode === 'login' ? (
          <LoginForm
            onLogin={login}
            onSwitchToRegister={() => setAuthMode('register')}
            onForgotPassword={() => setAuthMode('forgot-password')}
          />
        ) : authMode === 'register' ? (
          <RegisterForm
            onRegister={register}
            onSwitchToLogin={() => setAuthMode('login')}
          />
        ) : (
          <ForgotPassword
            onBackToLogin={() => setAuthMode('login')}
          />
        )}
      </AuthLayout>
    );
  }

  const handleDocumentSelect = (document: Document) => {
    setSelectedDocument(document);
    chat.createSession(document);
  };

  const handleSendMessage = (message: string) => {
    if (selectedDocument && chat.currentSession) {
      chat.sendMessage(message, selectedDocument).then(() => {
        setForceUpdate(f => f + 1);
      });
    }
  };

  // Add debugging log to check if messages are updating
  console.log("Current session:", chat.currentSession);
  console.log("Current session messages:", chat.currentSession?.messages);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
      <Header user={user} onLogout={logout} />
      
      <main className="max-w-[95%] mx-auto  py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 mt-[80px] gap-8">
          {/* Left Column - Document Management */}
          <div className="lg:col-span-1 space-y-6">
            <DocumentUpload
              onFileUpload={uploadDocument}
              onUrlUpload={uploadFromUrl}
              processingDocuments={processingDocuments}
            />
            
            <DocumentList
              documents={documents}
              processingDocuments={processingDocuments}
              onSelectDocument={handleDocumentSelect}
              onDeleteDocument={deleteDocument}
              selectedDocumentId={selectedDocument?.id}
            />
          </div>

          {/* Right Column - Chat Interface */}
          <div className="lg:col-span-2 sticky top-[100px] h-[530px]">
            {selectedDocument && chat.currentSession ? (
              <ChatInterface
                document={selectedDocument}
                messages={chat.currentSession.messages}
                isTyping={chat.isTyping}
                onSendMessage={handleSendMessage}
                chatSessions={chat.chatSessions}
                currentSessionId={chat.currentSession?.id}
                onSelectSession={chat.selectSession}
                onDeleteSession={chat.deleteSession}
                selectedDocId={selectedDocument.id}
              />
            ) : (
              <div className="sticky top-[100px]  bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-12 text-center h-[530px] flex items-center justify-center transition-colors duration-200">
                <div>
                  <div className="w-16 h-16 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-2xl">💬</span>
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                    Select a Document to Start Chatting
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400 max-w-md mx-auto">
                    Upload a document and select it from the list to begin asking questions. 
                    Our AI assistant will help you find the information you need.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function App() {
  return (
    <ThemeProvider>
      <Routes>
        <Route path="/login" element={<LoginForm />} />
        <Route path="/register" element={<RegisterForm />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="*" element={<AppContent />} />
      </Routes>
    </ThemeProvider>
  );
}

export default App;