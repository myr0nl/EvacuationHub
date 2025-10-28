import React from 'react';
import { ClipboardList } from 'lucide-react';
import './SidebarFAB.css';

/**
 * SidebarFAB - Floating Action Button for desktop sidebar
 *
 * A FAB that appears on desktop to toggle the sidebar visibility.
 * Hidden on mobile (<= 768px) where the sidebar is replaced by FilterBottomSheet.
 *
 * @param {function} onClick - Handler to toggle the sidebar
 * @param {boolean} isOpen - Whether the sidebar is currently open
 */
function SidebarFAB({ onClick, isOpen }) {
  return (
    <button
      className={`sidebar-fab ${isOpen ? 'active' : ''}`}
      onClick={onClick}
      aria-label={isOpen ? 'Close disaster list' : 'Open disaster list'}
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

export default SidebarFAB;
