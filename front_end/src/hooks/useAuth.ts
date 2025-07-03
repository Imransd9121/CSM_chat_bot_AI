import { useState, useEffect } from 'react';
import { User } from '../types';
import { useDocuments } from './useDocuments';

const API_URL = 'http://localhost:5000'; // Change this if your Flask backend runs elsewhere

export const useAuth = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const { resetDocuments } = useDocuments(token || undefined);

  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        return { success: false, error: data.detail || 'Login failed. Please try again.' };
      }
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      const userData: User = {
        id: data.email, // You may want to decode JWT for real id
        name: data.username,
        email: data.email,
        createdAt: new Date().toISOString(),
      };
      setUser(userData);
      localStorage.setItem('user', JSON.stringify(userData));
      return { success: true };
    } catch (err) {
      return { success: false, error: 'An error occurred. Please try again.' };
    }
  };

  const register = async (name: string, email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(`${API_URL}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username: name, email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        return { success: false, error: data.detail || 'Registration failed. Please try again.' };
      }
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      const userData: User = {
        id: email, // You may want to decode JWT for real id
        name,
        email,
        createdAt: new Date().toISOString(),
      };
      setUser(userData);
      localStorage.setItem('user', JSON.stringify(userData));
      return { success: true };
    } catch (err) {
      return { success: false, error: 'An error occurred. Please try again.' };
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    localStorage.removeItem('documents');
    localStorage.removeItem('chatSessions');
    resetDocuments();
  };

  return { user, loading, login, register, logout };
};