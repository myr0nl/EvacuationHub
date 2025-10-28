import React from 'react';
import { Star, Award, CheckCircle, Circle, AlertTriangle, XCircle } from 'lucide-react';
import './CredibilityBadge.css';

const CREDIBILITY_LEVELS = {
  Expert: {
    Icon: Star,
    color: '#FFD700',
    textColor: '#000',
    description: 'Expert Reporter (90-100): Highly trusted with exceptional reporting history',
    range: '90-100'
  },
  Veteran: {
    Icon: Award,
    color: '#C0C0C0',
    textColor: '#000',
    description: 'Veteran Reporter (75-89): Trusted reporter with strong track record',
    range: '75-89'
  },
  Trusted: {
    Icon: CheckCircle,
    color: '#27ae60',
    textColor: '#fff',
    description: 'Trusted Reporter (60-74): Reliable reporter with good accuracy',
    range: '60-74'
  },
  Neutral: {
    Icon: Circle,
    color: '#95a5a6',
    textColor: '#fff',
    description: 'Neutral Reporter (50-59): New or average reporter',
    range: '50-59'
  },
  Caution: {
    Icon: AlertTriangle,
    color: '#f39c12',
    textColor: '#fff',
    description: 'Caution (30-49): Reports may be less reliable',
    range: '30-49'
  },
  Unreliable: {
    Icon: XCircle,
    color: '#e74c3c',
    textColor: '#fff',
    description: 'Unreliable (0-29): Low credibility, verify with caution',
    range: '0-29'
  }
};

function CredibilityBadge({
  level = 'Neutral',
  score = 50,
  showScore = true,
  showTooltip = true,
  size = 'medium',
  inline = false
}) {
  const badgeInfo = CREDIBILITY_LEVELS[level] || CREDIBILITY_LEVELS.Neutral;

  const sizeClasses = {
    small: 'credibility-badge-small',
    medium: 'credibility-badge-medium',
    large: 'credibility-badge-large'
  };

  const IconComponent = badgeInfo.Icon;
  const iconSize = size === 'small' ? 14 : size === 'large' ? 20 : 16;

  return (
    <div
      className={`credibility-badge ${sizeClasses[size]} ${inline ? 'credibility-badge-inline' : ''}`}
      style={{
        backgroundColor: badgeInfo.color,
        color: badgeInfo.textColor
      }}
      title={showTooltip ? badgeInfo.description : ''}
    >
      <span className="credibility-icon">
        <IconComponent size={iconSize} strokeWidth={2} />
      </span>
      <span className="credibility-level">{level}</span>
      {showScore && (
        <span className="credibility-score">({score})</span>
      )}
    </div>
  );
}

export default CredibilityBadge;
