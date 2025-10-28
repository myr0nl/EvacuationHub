import React from 'react';
import { ClipboardList } from 'lucide-react';
import './MobileFilterFAB.css';

/**
 * MobileFilterFAB - Floating Action Button for mobile filter menu
 *
 * A touch-friendly FAB that appears only on mobile devices (<= 768px).
 * Opens the bottom sheet on click.
 *
 * @param {function} onClick - Handler to open the bottom sheet
 * @param {boolean} isOpen - Whether the bottom sheet is currently open
 */
function MobileFilterFAB({ onClick, isOpen }) {
  return (
    <button
      className={`mobile-filter-fab ${isOpen ? 'active' : ''}`}
      onClick={onClick}
      aria-label="Open filter menu"
      aria-expanded={isOpen}
      type="button"
    >
      <ClipboardList
        className="fab-icon"
        size={24}
        strokeWidth={2}
        aria-hidden="true"
      />
    </button>
  );
}

export default MobileFilterFAB;
