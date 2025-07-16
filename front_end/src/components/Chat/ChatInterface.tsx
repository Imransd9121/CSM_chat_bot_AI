import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, FileText, Clock, MessageCircle, Trash2 } from 'lucide-react';
import { Message, Document, ChatSession } from '../../types';
import axios from "axios";
import { franc } from 'franc-min';

interface ChatInterfaceProps {
  document: Document;
  messages: Message[];
  isTyping: boolean;
  onSendMessage: (message: string) => void;
  chatSessions: ChatSession[];
  currentSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  selectedDocId?: string;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  document,
  messages: parentMessages,
  isTyping: parentIsTyping,
  onSendMessage,
  chatSessions,
  currentSessionId,
  onSelectSession,
  onDeleteSession,
  selectedDocId
}) => {
  const [inputMessage, setInputMessage] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [question, setQuestion] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<any>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const silenceTimerRef = useRef<number | null>(null);
  const [localMessages, setLocalMessages] = useState(parentMessages || []);
  const [isTyping, setIsTyping] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [speakingWordIndex, setSpeakingWordIndex] = useState<number | null>(null);
  const [speechStatus, setSpeechStatus] = useState<string | null>(null);

  // Map franc language codes to BCP-47 codes for SpeechSynthesis
  const francToBCP47: Record<string, string> = {
    'eng': 'en-US',
    'hin': 'hi-IN',        // Hindi
    'ben': 'bn-IN',        // Bengali
    'tel': 'te-IN',        // Telugu
    'mar': 'mr-IN',        // Marathi
    'tam': 'ta-IN',        // Tamil
    'guj': 'gu-IN',        // Gujarati
    'kan': 'kn-IN',        // Kannada
    'mal': 'ml-IN',        // Malayalam
    'ori': 'or-IN',        // Odia
    'pan': 'pa-IN',        // Punjabi
    'asm': 'as-IN',        // Assamese
    'urd': 'ur-IN',        // Urdu
    'nep': 'ne-IN',        // Nepali
    'sin': 'si-LK',        // Sinhala (Sri Lanka)
    'fra': 'fr-FR',
    'spa': 'es-ES',
    'deu': 'de-DE',
    'ita': 'it-IT',
    'rus': 'ru-RU',
    'jpn': 'ja-JP',
    'kor': 'ko-KR',
    'cmn': 'zh-CN',
    // Add more as needed
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [localMessages, isTyping]);

  useEffect(() => {
    setLocalMessages(parentMessages || []);
  }, [parentMessages, document?.id, currentSessionId]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputMessage.trim()) {
      onSendMessage(inputMessage.trim());
      setInputMessage('');
    }
  };

  // Filter sessions for current document
  const documentSessions = chatSessions.filter(session => session.documentId === document.id);

  // Start speech recognition
  const startRecording = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechStatus("Speech recognition is not supported in this browser.");
      alert("Speech recognition is not supported in this browser.");
      console.error("Speech recognition is not supported in this browser.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      setIsRecording(true);
      setSpeechStatus("Listening... Speak now.");
      console.log("Speech recognition started");
    };
    recognition.onend = () => {
      setIsRecording(false);
      setSpeechStatus("Stopped listening.");
      console.log("Speech recognition ended");
      setTimeout(() => setSpeechStatus(null), 2000);
      if (inputRef.current) inputRef.current.focus();
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current!);
        silenceTimerRef.current = null;
      }
    };
    recognition.onerror = (event: any) => {
      setIsRecording(false);
      setSpeechStatus(`Speech recognition error: ${event.error}`);
      console.error("Speech recognition error:", event.error);
      setTimeout(() => setSpeechStatus(null), 3000);
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current!);
        silenceTimerRef.current = null;
      }
      if (event.error !== 'no-speech' && event.error !== 'aborted' && event.error !== 'audio-capture') {
        alert('Speech recognition error: ' + event.error);
      }
    };
    recognition.onresult = (event: any) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        transcript += event.results[i][0].transcript;
      }
      setQuestion(transcript); // This updates the input field in real time
      setSpeechStatus(`Heard: ${transcript}`);
      console.log("Speech recognition result:", transcript);
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current!);
      }
      silenceTimerRef.current = setTimeout(() => {
        if (recognitionRef.current) {
          recognitionRef.current.stop();
        }
      }, 5000); // 5 seconds of silence
    };
    recognitionRef.current = recognition;
    recognition.start();
    silenceTimerRef.current = setTimeout(() => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    }, 5000);
  };

  // Stop speech recognition
  const stopRecording = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current!);
      silenceTimerRef.current = null;
    }
  };

  // Send text question as before
  const sendText = async () => {
    if (!question.trim() || !selectedDocId) return;
    // Add user message locally
    const userMessage = {
      id: Math.random().toString(36).substr(2, 9),
      type: 'user' as 'user',
      content: question,
      timestamp: new Date().toISOString(),
      documentId: selectedDocId
    };
    setLocalMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);
    setQuestion("");
    try {
      const res = await axios.post("/chat", {
        doc_id: selectedDocId,
        question,
      }, {
        baseURL: "http://localhost:5000",
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("token")}`,
          "Content-Type": "application/json",
        },
      });
      // Add bot answer when received
      if (res.data.answer) {
        const botMessage = {
          id: Math.random().toString(36).substr(2, 9),
          type: 'bot' as 'bot',
          content: res.data.answer,
          timestamp: new Date().toISOString(),
          documentId: selectedDocId
        };
        setLocalMessages((prev) => [...prev, botMessage]);
      }
      setIsTyping(false);
    } catch (err: any) {
      setIsTyping(false);
      alert("Text chat failed: " + (err.response?.data?.detail || err.message));
    }
  };

  // Speak text using browser TTS with language detection and karaoke highlighting
  const speakText = (text: string, messageId: string) => {
    if ('speechSynthesis' in window) {
      // If already speaking this message, stop
      if (speakingMessageId === messageId) {
        window.speechSynthesis.cancel();
        setSpeakingMessageId(null);
        setSpeakingWordIndex(null);
        return;
      }
      // Stop any current speech and reset state
      window.speechSynthesis.cancel();
      setSpeakingMessageId(null);
      setSpeakingWordIndex(null);
      setTimeout(() => {
        // Detect language
        let lang = 'en-US';
        const francCode = franc(text);
        if (francCode && francCode !== 'und' && francToBCP47[francCode]) {
          lang = francToBCP47[francCode];
        }
        const utterance = new window.SpeechSynthesisUtterance(text);
        utterance.lang = lang;
        utterance.rate = 0.8;  // Slower for clarity
        utterance.pitch = 1.0; // Normal pitch
        utterance.volume = 1.0; // Full volume
        
        // Try to select a better voice for the language
        const voices = window.speechSynthesis.getVoices();
        const voice = voices.find(v => v.lang.startsWith(lang.split('-')[0]));
        if (voice) utterance.voice = voice;
        
        utterance.onend = () => {
          setSpeakingMessageId(null);
          setSpeakingWordIndex(null);
        };
        utterance.onerror = () => {
          setSpeakingMessageId(null);
          setSpeakingWordIndex(null);
        };
        utterance.onboundary = (event: any) => {
          if (event.name === 'word') {
            const upto = text.slice(0, event.charIndex);
            const wordIndex = upto.trim().length === 0 ? 0 : upto.trim().split(/\s+/).length;
            setSpeakingWordIndex(wordIndex);
          }
        };
        setSpeakingMessageId(messageId);
        setSpeakingWordIndex(0);
        window.speechSynthesis.speak(utterance);
      }, 0);
    } else {
      alert('Sorry, your browser does not support text-to-speech.');
    }
  };

  useEffect(() => {
    return () => {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      if (recognitionRef.current) {
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current = null;
      }
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current!);
        silenceTimerRef.current = null;
      }
    };
  }, []);

  return (
    <>
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 flex flex-col h-[600px] transition-colors duration-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 rounded-t-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <FileText className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white">{document.name}</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">Ask questions about this document</p>
            </div>
          </div>
          
          {documentSessions.length > 0 && (
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="flex items-center space-x-2 px-3 py-2 text-sm bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors duration-200"
            >
              <MessageCircle className="w-4 h-4" />
              <span>History ({documentSessions.length})</span>
            </button>
          )}
        </div>
      </div>

      {/* Chat History Sidebar */}
      {showHistory && documentSessions.length > 0 && (
        <div className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/30 p-4">
          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Previous Conversations</h4>
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {documentSessions.map((session) => {
              const isSelected = currentSessionId === session.id;
              const lastMessage = session.messages[session.messages.length - 1];
              
              return (
                <div
                  key={session.id}
                  className={`p-3 rounded-lg border transition-all duration-200 cursor-pointer ${
                    isSelected
                      ? 'border-blue-200 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                  onClick={() => onSelectSession(session.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      {lastMessage && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 truncate mb-1">
                          {lastMessage.content}
                        </p>
                      )}
                      
                      <div className="flex items-center space-x-1 text-xs text-gray-500 dark:text-gray-500">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(session.updatedAt).toLocaleDateString()}</span>
                        <span>•</span>
                        <span>{session.messages.length} messages</span>
                      </div>
                    </div>
                    
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(session.id);
                      }}
                      className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors duration-200"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {localMessages.length === 0 ? (
          <div className="text-center py-8">
            <Bot className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
            <p className="text-gray-600 dark:text-gray-400 mb-2">Hi! I'm your AI assistant.</p>
            <p className="text-sm text-gray-500 dark:text-gray-500">
              Ask me anything about "{document.name}" and I'll help you find the information you need.
            </p>
          </div>
        ) : (
            localMessages.map((message) => (
            <div
              key={message.id}
              className={`flex items-start space-x-3 ${
                message.type === 'user' ? 'flex-row-reverse space-x-reverse' : ''
              }`}
            >
              <div
                className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  message.type === 'user'
                    ? 'bg-blue-600'
                    : 'bg-gray-200 dark:bg-gray-700'
                }`}
              >
                {message.type === 'user' ? (
                  <User className="w-4 h-4 text-white" />
                ) : (
                  <Bot className="w-4 h-4 text-gray-600 dark:text-gray-300" />
                )}
              </div>
              
              <div
                className={`flex-1 max-w-xs md:max-w-md lg:max-w-lg ${
                  message.type === 'user' ? 'text-right' : ''
                }`}
              >
                <div
                  className={`inline-block p-3 rounded-lg ${
                    message.type === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                  }`}
                >
                    <p className="text-sm whitespace-pre-wrap">
                      {message.type === 'bot' && speakingMessageId === message.id && speakingWordIndex !== null
                        ? (() => {
                            const words = message.content.split(/(\s+)/);
                            return words.map((word, idx) =>
                              // Only bold non-space words
                              /\S/.test(word) && Math.floor(idx / 2) === speakingWordIndex
                                ? <b key={idx} style={{ color: '#2563eb' }}>{word}</b>
                                : <span key={idx}>{word}</span>
                            );
                          })()
                        : message.content}
                    </p>
                    {message.type === 'bot' && (
                      <>
                        <button
                          onClick={() => speakText(message.content, message.id)}
                          title={speakingMessageId === message.id ? "Stop reading" : "Listen to answer"}
                          style={{
                            marginLeft: 8,
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            borderRadius: '50%',
                            transition: 'background 0.2s',
                            display: 'inline-flex',
                            alignItems: 'center',
                          }}
                        >
                          <span role="img" aria-label="Speaker">
                            {speakingMessageId === message.id ? '🔈' : '🔊'}
                          </span>
                          {speakingMessageId === message.id && (
                            <span className="heart-rate-animation" style={{ marginLeft: 8 }}>
                              <svg width="120" height="24" viewBox="0 0 120 24">
                                <polyline
                                  points="0,12 15,12 22,2 36,22 50,12 64,12 72,4 88,20 104,12 120,12"
                                  fill="none"
                                  stroke="#0ea5e9"
                                  strokeWidth="2"
                                  strokeLinejoin="round"
                                >
                                  <animate
                                    attributeName="points"
                                    dur="0.5s"
                                    repeatCount="indefinite"
                                    values="
                                      0,12 15,12 22,2 36,22 50,12 64,12 72,4 88,20 104,12 120,12;
                                      0,12 15,12 22,20 36,2 50,12 64,12 72,20 88,4 104,12 120,12;
                                      0,12 15,12 22,2 36,22 50,12 64,12 72,4 88,20 104,12 120,12
                                    "
                                  />
                                </polyline>
                              </svg>
                            </span>
                          )}
                        </button>
                      </>
                    )}
                </div>
                
                <div className={`flex items-center space-x-1 mt-1 text-xs text-gray-500 dark:text-gray-500 ${
                  message.type === 'user' ? 'justify-end' : ''
                }`}>
                  <Clock className="w-3 h-3" />
                    <span>{new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              </div>
            </div>
          ))
        )}

        {isTyping && (
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
              <Bot className="w-4 h-4 text-gray-600 dark:text-gray-300" />
            </div>
            <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "8px",
            borderTop: "1px solid #eee",
            background: "#fff",
          }}
        >
          <input
            ref={inputRef}
            type="text"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="Type your question"
            disabled={isRecording}
            style={{
              flex: 1,
              padding: "10px",
              borderRadius: "20px",
              border: "1px solid #ccc",
              outline: "none",
              fontSize: "1rem",
            }}
            onKeyDown={e => {
              if (e.key === "Enter" && question.trim() && !isRecording) sendText();
            }}
          />
          <button
            onClick={sendText}
            disabled={isRecording || !question.trim()}
            className="relative w-14 h-7 bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 text-white rounded-full p-1 transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800 flex items-center justify-center ml-1"
            title="Send"
          >
            <span role="img" aria-label="Send">📤</span>
          </button>
          <button
            onClick={isRecording ? stopRecording : startRecording}
            className={`relative w-14 h-7 flex items-center justify-center ${isRecording ? 'bg-red-500' : 'bg-gray-200 dark:bg-gray-700'} text-${isRecording ? 'white' : 'gray-800'} rounded-full p-1 transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800 ml-1`}
            title={isRecording ? "Stop Recording" : "Record Audio"}
          >
            {isRecording ? (
              <span role="img" aria-label="Recording">🔴</span>
            ) : (
              <span role="img" aria-label="Mic">🎤</span>
            )}
          </button>
        </div>
        {speechStatus && (
          <div style={{ textAlign: 'center', color: '#2563eb', margin: '8px 0', fontWeight: 500 }}>
            {speechStatus}
          </div>
        )}
      </div>
    </>
  );
};