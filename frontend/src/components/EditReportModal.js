import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import './EditReportModal.css';

function EditReportModal({ report, onClose, onSave, currentUser }) {
  const [formData, setFormData] = useState({
    type: '',
    severity: '',
    description: '',
    affected_population: '',
    image_url: '',
    ai_reasoning: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Initialize form data when report changes
  useEffect(() => {
    if (report) {
      setFormData({
        type: report.type || report.disaster_type || '',
        severity: report.severity || '',
        description: report.description || '',
        affected_population: report.affected_population || '',
        image_url: report.image_url || '',
        ai_reasoning: report.confidence_breakdown?.ai_enhancement?.reasoning || ''
      });
    }
  }, [report]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Prepare update data
      const updates = {
        type: formData.type,
        severity: formData.severity,
        description: formData.description,
        affected_population: formData.affected_population ? parseInt(formData.affected_population) : null,
        image_url: formData.image_url || null
      };

      // If AI reasoning was edited, include it
      if (formData.ai_reasoning !== (report.confidence_breakdown?.ai_enhancement?.reasoning || '')) {
        updates.ai_reasoning = formData.ai_reasoning;
      }

      await onSave(report.id, updates);
      onClose();
    } catch (err) {
      console.error('Error updating report:', err);
      setError(err.message || 'Failed to update report');
    } finally {
      setLoading(false);
    }
  };

  if (!report) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content edit-report-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Edit Report</h2>
          <button className="modal-close-button" onClick={onClose} aria-label="Close">
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="edit-report-form">
          {error && (
            <div className="alert alert-error">
              {error}
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="type">Disaster Type *</label>
              <select
                id="type"
                name="type"
                value={formData.type}
                onChange={handleChange}
                required
              >
                <option value="">Select type...</option>
                <option value="earthquake">Earthquake</option>
                <option value="flood">Flood</option>
                <option value="wildfire">Wildfire</option>
                <option value="hurricane">Hurricane</option>
                <option value="tornado">Tornado</option>
                <option value="volcano">Volcano</option>
                <option value="drought">Drought</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="severity">Severity *</label>
              <select
                id="severity"
                name="severity"
                value={formData.severity}
                onChange={handleChange}
                required
              >
                <option value="">Select severity...</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="4"
              placeholder="Describe what you observed..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="affected_population">Affected Population (estimate)</label>
            <input
              type="number"
              id="affected_population"
              name="affected_population"
              value={formData.affected_population}
              onChange={handleChange}
              placeholder="e.g., 1000"
              min="0"
            />
          </div>

          <div className="form-group">
            <label htmlFor="image_url">Image URL</label>
            <input
              type="url"
              id="image_url"
              name="image_url"
              value={formData.image_url}
              onChange={handleChange}
              placeholder="https://example.com/image.jpg"
            />
          </div>

          {report.confidence_breakdown?.ai_enhancement && (
            <div className="form-group">
              <label htmlFor="ai_reasoning">
                AI Analysis
                <span className="label-hint">(Edit to override AI-generated reasoning)</span>
              </label>
              <textarea
                id="ai_reasoning"
                name="ai_reasoning"
                value={formData.ai_reasoning}
                onChange={handleChange}
                rows="3"
                placeholder="AI-generated analysis will appear here..."
              />
              <small className="form-hint">
                This will override the automatically generated AI analysis shown to users.
              </small>
            </div>
          )}

          <div className="form-info">
            <p><strong>Location:</strong> {report.latitude?.toFixed(4)}, {report.longitude?.toFixed(4)}</p>
            <p><strong>Reported:</strong> {new Date(report.reported_at || report.timestamp).toLocaleString()}</p>
            {report.user_display_name && (
              <p><strong>Reported by:</strong> {report.user_display_name}</p>
            )}
          </div>

          <div className="modal-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={loading}
            >
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default EditReportModal;
