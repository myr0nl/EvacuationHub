import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import CredibilityBadge from './CredibilityBadge';
import './UserProfile.css';

function UserProfile() {
  const navigate = useNavigate();
  const { currentUser, userProfile, logout, refreshProfile } = useAuth();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!currentUser) {
      navigate('/login');
    }
  }, [currentUser, navigate]);

  useEffect(() => {
    // Refresh profile data when component mounts
    refreshProfile();
  }, []);

  if (!userProfile) {
    return (
      <div className="profile-container">
        <div className="loading">Loading profile...</div>
      </div>
    );
  }

  const handleLogout = async () => {
    setLoading(true);
    try {
      await logout();
      navigate('/');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setLoading(false);
    }
  };

  const calculateAccuracyRate = () => {
    // TODO: Calculate from actual report data
    // For now, estimate based on credibility score
    const baseAccuracy = 60;
    const credibilityBonus = (userProfile.credibilityScore - 50) * 0.5;
    return Math.min(95, Math.max(40, baseAccuracy + credibilityBonus));
  };

  const getProgressColor = (score) => {
    if (score >= 90) return '#FFD700'; // Gold
    if (score >= 75) return '#C0C0C0'; // Silver
    if (score >= 60) return '#27ae60'; // Green
    if (score >= 50) return '#95a5a6'; // Gray
    if (score >= 30) return '#f39c12'; // Orange
    return '#e74c3c'; // Red
  };

  const progressPercentage = userProfile.credibilityScore;
  const progressColor = getProgressColor(userProfile.credibilityScore);

  return (
    <div className="profile-container">
      <div className="profile-header">
        <button onClick={() => navigate('/')} className="back-button">
          ← Back to Map
        </button>
        <h1>User Profile</h1>
      </div>

      <div className="profile-content">
        {/* User Info Card */}
        <div className="profile-card">
          <div className="profile-avatar">
            {userProfile.displayName.charAt(0).toUpperCase()}
          </div>
          <div className="profile-info">
            <h2>{userProfile.displayName}</h2>
            <p className="profile-email">{userProfile.email}</p>
          </div>
        </div>

        {/* Credibility & Statistics Combined Card */}
        <div className="profile-card credibility-stats-card">
          <div className="credibility-stats-layout">
            {/* Left side: Credibility Score */}
            <div className="credibility-section">
              <h3>Credibility Score</h3>

              <div className="credibility-display">
                <div className="credibility-progress-circle">
                  <svg width="200" height="200" viewBox="0 0 200 200">
                    <circle
                      cx="100"
                      cy="100"
                      r="80"
                      fill="none"
                      stroke="#e0e0e0"
                      strokeWidth="20"
                    />
                    <circle
                      cx="100"
                      cy="100"
                      r="80"
                      fill="none"
                      stroke={progressColor}
                      strokeWidth="20"
                      strokeDasharray={`${progressPercentage * 5.024} 502.4`}
                      strokeLinecap="round"
                      transform="rotate(-90 100 100)"
                      style={{ transition: 'stroke-dasharray 1s ease' }}
                    />
                  </svg>
                  <div className="credibility-score-text">
                    <div className="score-number">{userProfile.credibilityScore}</div>
                    <div className="score-label">out of 100</div>
                  </div>
                </div>

                <div className="credibility-level-display">
                  <CredibilityBadge
                    level={userProfile.credibilityLevel}
                    score={userProfile.credibilityScore}
                    showScore={false}
                    size="large"
                  />
                </div>
              </div>

              <div className="credibility-explanation">
                <p>
                  Your credibility score reflects the accuracy and reliability of your disaster reports.
                  Higher scores give your reports more influence on the confidence system.
                </p>
              </div>
            </div>

            {/* Right side: Reporting Statistics */}
            <div className="statistics-section">
              <h3>Reporting Statistics</h3>

              <div className="stats-grid">
                <div className="stat-item">
                  <div className="stat-value">{userProfile.totalReports}</div>
                  <div className="stat-label">Total Reports</div>
                </div>

                <div className="stat-item">
                  <div className="stat-value">{Math.round(calculateAccuracyRate())}%</div>
                  <div className="stat-label">Accuracy Rate</div>
                </div>

                <div className="stat-item">
                  <div className="stat-value">
                    {userProfile.credibilityScore >= 80 ? (
                      Math.round(userProfile.credibilityScore / 10)
                    ) : (
                      '-'
                    )}
                  </div>
                  <div className="stat-label">Successful Reports</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="profile-actions">
          <button
            onClick={handleLogout}
            className="logout-button"
            disabled={loading}
          >
            {loading ? 'Logging out...' : 'Logout'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default UserProfile;
