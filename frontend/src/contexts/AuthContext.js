import React, { createContext, useContext, useState, useEffect } from 'react';
import { subscribeToAuthChanges, signOutUser, getIdToken } from '../firebase';
import { getUserProfile } from '../services/api';

const AuthContext = createContext();

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [userProfile, setUserProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch user profile from backend
  const fetchUserProfile = async (firebaseUser) => {
    try {
      const token = await firebaseUser.getIdToken();
      const profile = await getUserProfile(token);

      setUserProfile({
        uid: firebaseUser.uid,
        email: firebaseUser.email,
        displayName: firebaseUser.displayName || profile.display_name || 'Anonymous User',
        credibilityScore: profile.credibility_score || 50,
        credibilityLevel: profile.credibility_level || 'Neutral',
        totalReports: profile.total_reports || 0,
        badges: profile.badges || [],
        createdAt: profile.created_at
      });
    } catch (error) {
      console.error('Error fetching user profile:', error);
      // Set basic profile from Firebase if backend fails
      setUserProfile({
        uid: firebaseUser.uid,
        email: firebaseUser.email,
        displayName: firebaseUser.displayName || 'Anonymous User',
        credibilityScore: 50,
        credibilityLevel: 'Neutral',
        totalReports: 0,
        badges: []
      });
    }
  };

  useEffect(() => {
    const unsubscribe = subscribeToAuthChanges(async (firebaseUser) => {
      setCurrentUser(firebaseUser);

      if (firebaseUser) {
        await fetchUserProfile(firebaseUser);
      } else {
        setUserProfile(null);
      }

      setLoading(false);
    });

    return unsubscribe;
  }, []);

  const login = async (email, password) => {
    try {
      setError(null);
      // Firebase sign-in handled by AuthContext subscription
      const { signInWithEmail } = require('../firebase');
      const user = await signInWithEmail(email, password);
      await fetchUserProfile(user);
      return user;
    } catch (error) {
      setError(error.message);
      throw error;
    }
  };

  const register = async (email, password, displayName) => {
    try {
      setError(null);
      const { signUpWithEmail } = require('../firebase');
      const user = await signUpWithEmail(email, password, displayName);
      await fetchUserProfile(user);
      return user;
    } catch (error) {
      setError(error.message);
      throw error;
    }
  };

  const logout = async () => {
    try {
      setError(null);
      await signOutUser();
      setCurrentUser(null);
      setUserProfile(null);
    } catch (error) {
      setError(error.message);
      throw error;
    }
  };

  const refreshProfile = async () => {
    if (currentUser) {
      await fetchUserProfile(currentUser);
    }
  };

  const value = {
    currentUser,
    userProfile,
    loading,
    error,
    login,
    register,
    logout,
    refreshProfile,
    getIdToken: () => getIdToken()
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
}
