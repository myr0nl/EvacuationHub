import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { RefreshCw, Database, Trash2, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import './AdminPanel.css';

/**
 * Admin Panel - Cache Management and System Controls
 * Only accessible to users with admin custom claims
 */
function AdminPanel() {
  const { currentUser } = useAuth();
  const [cacheStatus, setCacheStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState({});
  const [clearing, setClearing] = useState({});
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  // Fetch cache status on mount
  useEffect(() => {
    fetchCacheStatus();
  }, []);

  const fetchCacheStatus = async () => {
    try {
      setLoading(true);
      const response = await fetch('https://alerter-production.up.railway.app/api/cache/status');
      const data = await response.json();
      setCacheStatus(data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch cache status:', err);
      setError('Failed to load cache status');
    } finally {
      setLoading(false);
    }
  };

  const refreshCache = async (type) => {
    try {
      setRefreshing({ ...refreshing, [type]: true });
      setMessage(null);
      setError(null);

      const token = await currentUser.getIdToken();

      const response = await fetch('https://alerter-production.up.railway.app/api/cache/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ type })
      });

      const data = await response.json();

      if (response.ok) {
        setMessage(`✓ ${type} cache refreshed successfully: ${JSON.stringify(data)}`);
        // Refresh cache status to show updated counts
        await fetchCacheStatus();
      } else {
        setError(`Failed to refresh ${type}: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Failed to refresh cache:', err);
      setError(`Failed to refresh ${type}: ${err.message}`);
    } finally {
      setRefreshing({ ...refreshing, [type]: false });
    }
  };

  const clearCache = async (type) => {
    if (!window.confirm(`Are you sure you want to clear ${type} cache?`)) {
      return;
    }

    try {
      setClearing({ ...clearing, [type]: true });
      setMessage(null);
      setError(null);

      const token = await currentUser.getIdToken();

      const response = await fetch('https://alerter-production.up.railway.app/api/cache/clear', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ type })
      });

      const data = await response.json();

      if (response.ok) {
        setMessage(`✓ ${type} cache cleared successfully`);
        await fetchCacheStatus();
      } else {
        setError(`Failed to clear ${type}: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Failed to clear cache:', err);
      setError(`Failed to clear ${type}: ${err.message}`);
    } finally {
      setClearing({ ...clearing, [type]: false });
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const formatDuration = (minutes) => {
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    return `${hours} hr`;
  };

  const getStatusIcon = (count) => {
    if (count === 0) return <XCircle size={16} color="#ef4444" />;
    if (count < 10) return <AlertCircle size={16} color="#f59e0b" />;
    return <CheckCircle size={16} color="#10b981" />;
  };

  if (loading) {
    return (
      <div className="admin-panel">
        <div className="admin-header">
          <Database size={24} />
          <h2>Admin Panel</h2>
        </div>
        <div className="loading-message">Loading cache status...</div>
      </div>
    );
  }

  return (
    <div className="admin-panel">
      <div className="admin-header">
        <Database size={24} />
        <h2>Cache Management</h2>
        <button onClick={fetchCacheStatus} className="btn-icon" title="Refresh status">
          <RefreshCw size={18} />
        </button>
      </div>

      {message && (
        <div className="alert alert-success">
          {message}
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      <div className="cache-grid">
        {cacheStatus && Object.entries(cacheStatus).map(([key, data]) => (
          <div key={key} className="cache-card">
            <div className="cache-card-header">
              <div className="cache-title">
                {getStatusIcon(data.count)}
                <h3>{key.replace(/_/g, ' ').toUpperCase()}</h3>
              </div>
              <div className="cache-count">{data.count}</div>
            </div>

            <div className="cache-details">
              <div className="detail-row">
                <span className="label">Last Updated:</span>
                <span className="value">{formatTimestamp(data.last_updated)}</span>
              </div>
              <div className="detail-row">
                <span className="label">Cache Duration:</span>
                <span className="value">{formatDuration(data.cache_duration_minutes)}</span>
              </div>
              {data.cleanup_run_at && (
                <div className="detail-row">
                  <span className="label">Last Cleanup:</span>
                  <span className="value">{formatTimestamp(data.cleanup_run_at)}</span>
                </div>
              )}
              {data.removed_count !== undefined && (
                <div className="detail-row">
                  <span className="label">Removed (cleanup):</span>
                  <span className="value">{data.removed_count}</span>
                </div>
              )}
            </div>

            <div className="cache-actions">
              <button
                onClick={() => refreshCache(key)}
                disabled={refreshing[key]}
                className="btn-primary btn-sm"
              >
                {refreshing[key] ? (
                  <>
                    <RefreshCw size={14} className="spinning" />
                    Refreshing...
                  </>
                ) : (
                  <>
                    <RefreshCw size={14} />
                    Refresh
                  </>
                )}
              </button>
              <button
                onClick={() => clearCache(key)}
                disabled={clearing[key]}
                className="btn-danger btn-sm"
              >
                {clearing[key] ? (
                  <>
                    <Trash2 size={14} />
                    Clearing...
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    Clear
                  </>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="admin-actions">
        <button
          onClick={() => refreshCache('all')}
          disabled={refreshing['all']}
          className="btn-primary"
        >
          {refreshing['all'] ? (
            <>
              <RefreshCw size={18} className="spinning" />
              Refreshing All Caches...
            </>
          ) : (
            <>
              <RefreshCw size={18} />
              Refresh All Caches
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default AdminPanel;
