/**
 * Tests for OfflineIndicator Component
 *
 * Run with: npm test OfflineIndicator.test.js
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import OfflineIndicator from '../OfflineIndicator';

describe('OfflineIndicator', () => {
  beforeEach(() => {
    jest.clearAllTimers();
    jest.clearAllMocks();
    // Default to online
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true,
    });
  });

  afterEach(() => {
    jest.clearAllTimers();
  });

  describe('Online/Offline Detection', () => {
    it('should not display banner when online', () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      });

      const { container } = render(<OfflineIndicator />);

      expect(container.firstChild).toBeNull();
    });

    it('should display banner when offline', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      render(<OfflineIndicator />);

      // Simulate offline event
      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/You're offline/)).toBeInTheDocument();
      });
    });

    it('should hide banner when coming back online', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      const { container } = render(<OfflineIndicator />);

      // Simulate offline event
      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/You're offline/)).toBeInTheDocument();
      });

      // Simulate coming back online
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      });
      fireEvent.online(window);

      await waitFor(() => {
        expect(container.firstChild).toBeNull();
      });
    });
  });

  describe('Offline Icon', () => {
    it('should display offline icon when offline', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        const svg = screen.getByText(/You're offline/).parentElement.querySelector('svg');
        expect(svg).toBeInTheDocument();
        expect(svg).toHaveAttribute('viewBox');
      });
    });
  });

  describe('Cache Age Display', () => {
    beforeEach(() => {
      global.fetch = jest.fn();
    });

    afterEach(() => {
      jest.resetAllMocks();
    });

    it('should display cache age when available', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch.mockResolvedValueOnce({
        headers: new Map([['X-Cache-Age-Ms', '300000']]), // 5 minutes
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/last updated.*ago/)).toBeInTheDocument();
      });
    });

    it('should format cache age in minutes', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch.mockResolvedValueOnce({
        headers: new Map([['X-Cache-Age-Ms', '120000']]), // 2 minutes
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/2m ago/)).toBeInTheDocument();
      });
    });

    it('should format cache age in hours and minutes', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch.mockResolvedValueOnce({
        headers: new Map([['X-Cache-Age-Ms', '5400000']]), // 1h 30m
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/1h 30m ago/)).toBeInTheDocument();
      });
    });

    it('should display "Unknown" when fetch fails', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch.mockRejectedValueOnce(new Error('Network error'));

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/last updated Unknown/)).toBeInTheDocument();
      });
    });

    it('should handle missing cache age header', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch.mockResolvedValueOnce({
        headers: new Map(), // No cache age header
      });

      const { container } = render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        // Should show offline message without cache age
        expect(screen.getByText(/You're offline/)).toBeInTheDocument();
      });
    });

    it('should update cache age every minute when offline', async () => {
      jest.useFakeTimers();
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch
        .mockResolvedValueOnce({
          headers: new Map([['X-Cache-Age-Ms', '60000']]), // 1 minute
        })
        .mockResolvedValueOnce({
          headers: new Map([['X-Cache-Age-Ms', '120000']]), // 2 minutes
        });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/1m ago/)).toBeInTheDocument();
      });

      // Advance by 1 minute
      jest.advanceTimersByTime(60000);

      await waitFor(() => {
        expect(screen.getByText(/2m ago/)).toBeInTheDocument();
      });

      jest.useRealTimers();
    });
  });

  describe('Dismiss Functionality', () => {
    it('should hide banner when dismiss button clicked', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      const { container } = render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/You're offline/)).toBeInTheDocument();
      });

      const dismissButton = screen.getByLabelText(/Dismiss offline notification/);
      fireEvent.click(dismissButton);

      await waitFor(() => {
        expect(container.firstChild).toBeNull();
      });
    });

    it('should have accessible dismiss button', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        const dismissButton = screen.getByLabelText(/Dismiss offline notification/);
        expect(dismissButton).toHaveAttribute('aria-label');
      });
    });

    it('should show banner again after dismissing if still offline', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      const { rerender } = render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/You're offline/)).toBeInTheDocument();
      });

      // Dismiss banner
      const dismissButton = screen.getByLabelText(/Dismiss offline notification/);
      fireEvent.click(dismissButton);

      // Banner should be hidden but come back when remounting
      rerender(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/You're offline/)).toBeInTheDocument();
      });
    });
  });

  describe('Auto-Hide on Online', () => {
    it('should auto-hide banner immediately when going online', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      const { container } = render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/You're offline/)).toBeInTheDocument();
      });

      // Go back online
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      });

      fireEvent.online(window);

      await waitFor(() => {
        expect(container.firstChild).toBeNull();
      });
    });
  });

  describe('Styling', () => {
    it('should have fixed positioning', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      const { container } = render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        const banner = container.querySelector('div[style*="position: fixed"]');
        expect(banner).toBeInTheDocument();
        expect(banner).toHaveStyle('position: fixed');
        expect(banner).toHaveStyle('top: 0px');
        expect(banner).toHaveStyle('left: 0px');
        expect(banner).toHaveStyle('right: 0px');
      });
    });

    it('should have high z-index for visibility', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      const { container } = render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        const banner = container.querySelector('div[style*="z-index"]');
        expect(banner).toBeInTheDocument();
        expect(banner).toHaveStyle('z-index: 10000');
      });
    });

    it('should have orange background color', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      const { container } = render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        const banner = container.querySelector('div[style*="background-color"]');
        expect(banner).toBeInTheDocument();
        expect(banner).toHaveStyle('background-color: rgb(255, 152, 0)');
      });
    });

    it('should have flex layout', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        const banner = screen.getByText(/You're offline/).closest('div');
        expect(banner).toHaveStyle({
          display: 'flex',
        });
      });
    });
  });

  describe('Event Listeners', () => {
    it('should cleanup event listeners on unmount', () => {
      const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener');

      const { unmount } = render(<OfflineIndicator />);

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('online', expect.any(Function));
      expect(removeEventListenerSpy).toHaveBeenCalledWith('offline', expect.any(Function));

      removeEventListenerSpy.mockRestore();
    });

    it('should cleanup interval on unmount when offline', async () => {
      jest.useFakeTimers();
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      const { unmount } = render(<OfflineIndicator />);

      fireEvent.offline(window);

      unmount();

      // Should not throw when advancing timers
      expect(() => {
        jest.advanceTimersByTime(60000);
      }).not.toThrow();

      jest.useRealTimers();
    });
  });

  describe('Edge Cases', () => {
    it('should handle null cache age header', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        headers: {
          get: jest.fn().mockReturnValueOnce(null),
        },
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/You're offline/)).toBeInTheDocument();
      });
    });

    it('should handle rapid online/offline transitions', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      });

      const { container, rerender } = render(<OfflineIndicator />);

      // Go offline
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });
      fireEvent.offline(window);

      // Come back online before state updates
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      });
      fireEvent.online(window);

      await waitFor(() => {
        expect(container.firstChild).toBeNull();
      });
    });
  });

  describe('Message Content', () => {
    it('should display informative offline message', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/You're offline - showing cached disaster data/)).toBeInTheDocument();
      });
    });

    it('should include cache age in message when available', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        headers: new Map([['X-Cache-Age-Ms', '300000']]),
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        const text = screen.getByText(/You're offline - showing cached disaster data/);
        expect(text.textContent).toContain('last updated');
      });
    });
  });
});
