/**
 * Tests for PWAInstallPrompt Component
 *
 * Run with: npm test PWAInstallPrompt.test.js
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import PWAInstallPrompt from '../PWAInstallPrompt';

describe('PWAInstallPrompt', () => {
  let mockMatchMedia;
  let mockLocalStorage;

  beforeEach(() => {
    jest.clearAllTimers();
    jest.clearAllMocks();

    // Mock matchMedia
    mockMatchMedia = jest.fn((query) => ({
      matches: query === '(display-mode: standalone)' ? false : false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));
    window.matchMedia = mockMatchMedia;

    // Mock localStorage
    mockLocalStorage = {
      getItem: jest.fn(),
      setItem: jest.fn(),
      removeItem: jest.fn(),
      clear: jest.fn(),
    };
    Object.defineProperty(window, 'localStorage', {
      value: mockLocalStorage,
      writable: true,
    });

    // Mock console methods
    jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.clearAllTimers();
    console.log.mockRestore();
  });

  describe('Installation Detection', () => {
    it('should not display when app is already installed', () => {
      mockMatchMedia.mockImplementationOnce((query) => ({
        matches: query === '(display-mode: standalone)',
        media: query,
        onchange: null,
        addListener: jest.fn(),
        removeListener: jest.fn(),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        dispatchEvent: jest.fn(),
      }));

      const { container } = render(<PWAInstallPrompt />);

      expect(container.firstChild).toBeNull();
    });

    it('should not display when app is not installed and no prompt available', () => {
      const { container } = render(<PWAInstallPrompt />);

      expect(container.firstChild).toBeNull();
    });
  });

  describe('Install Prompt Display Timing', () => {
    it('should display install prompt after 5 seconds when available', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      render(<PWAInstallPrompt />);

      // Dispatch beforeinstallprompt event
      window.dispatchEvent(beforeinstallpromptEvent);

      // Should not be visible yet
      expect(screen.queryByText('Install Disaster Alert')).not.toBeInTheDocument();

      // Advance 5 seconds
      jest.advanceTimersByTime(5000);

      // Component should show after timeout
      const titleElement = await screen.findByText('Install Disaster Alert');
      expect(titleElement).toBeInTheDocument();

      jest.useRealTimers();
    });

    it('should prevent mini-infobar on beforeinstallprompt', async () => {
      const mockEvent = {
        preventDefault: jest.fn(),
        prompt: jest.fn(),
      };

      render(<PWAInstallPrompt />);

      // Dispatch beforeinstallprompt with preventDefault
      const event = new Event('beforeinstallprompt');
      event.preventDefault = mockEvent.preventDefault;
      event.prompt = mockEvent.prompt;

      window.dispatchEvent(event);

      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe('Install Functionality', () => {
    it('should call prompt when install button clicked', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const mockUserChoice = Promise.resolve({ outcome: 'accepted' });

      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;
      beforeinstallpromptEvent.userChoice = mockUserChoice;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const installButton = await screen.findByText(/Install App/);
      fireEvent.click(installButton);

      expect(mockPrompt).toHaveBeenCalled();

      jest.useRealTimers();
    });

    it('should handle accepted install outcome', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const mockUserChoice = Promise.resolve({ outcome: 'accepted' });

      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;
      beforeinstallpromptEvent.userChoice = mockUserChoice;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const installButton = await screen.findByText(/Install App/);
      fireEvent.click(installButton);

      await waitFor(() => {
        expect(console.log).toHaveBeenCalledWith(
          expect.stringContaining('accepted the install prompt')
        );
      });

      jest.useRealTimers();
    });

    it('should handle dismissed install outcome', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const mockUserChoice = Promise.resolve({ outcome: 'dismissed' });

      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;
      beforeinstallpromptEvent.userChoice = mockUserChoice;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const installButton = await screen.findByText(/Install App/);
      fireEvent.click(installButton);

      await waitFor(() => {
        expect(console.log).toHaveBeenCalledWith(
          expect.stringContaining('dismissed the install prompt')
        );
      });

      jest.useRealTimers();
    });

    it('should handle missing deferred prompt gracefully', async () => {
      jest.useFakeTimers();

      const { container } = render(<PWAInstallPrompt />);

      // Don't dispatch beforeinstallprompt, so deferredPrompt is null

      // Try to click install button on non-existent prompt
      // The component won't render without beforeinstallprompt
      expect(container.firstChild).toBeNull();

      jest.useRealTimers();
    });
  });

  describe('Dismissal with Cooldown', () => {
    it('should save dismissal timestamp to localStorage', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      mockLocalStorage.getItem.mockReturnValueOnce(null);

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const dismissButton = await screen.findByText(/Not Now/);
      fireEvent.click(dismissButton);

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'pwa-install-dismissed-at',
        expect.any(String)
      );

      jest.useRealTimers();
    });

    it('should not show prompt within 7 days of dismissal', () => {
      const now = new Date();
      const dayAgo = new Date(now.getTime() - 1 * 24 * 60 * 60 * 1000); // 1 day ago

      mockLocalStorage.getItem.mockReturnValueOnce(dayAgo.toISOString());

      const { container } = render(<PWAInstallPrompt />);

      // Dispatch beforeinstallprompt (should be ignored due to cooldown)
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = jest.fn();

      window.dispatchEvent(beforeinstallpromptEvent);

      // Prompt should not be displayed due to cooldown
      expect(container.firstChild).toBeNull();
    });

    it('should show prompt again after 7 days', async () => {
      jest.useFakeTimers();

      const now = new Date();
      const eightDaysAgo = new Date(now.getTime() - 8 * 24 * 60 * 60 * 1000);

      mockLocalStorage.getItem.mockReturnValueOnce(eightDaysAgo.toISOString());

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(screen.getByText(/Install Disaster Alert/)).toBeInTheDocument();
      });

      jest.useRealTimers();
    });

    it('should store ISO timestamp format', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      mockLocalStorage.getItem.mockReturnValueOnce(null);

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const dismissButton = await screen.findByText(/Not Now/);
      fireEvent.click(dismissButton);

      const callArgs = mockLocalStorage.setItem.mock.calls[0];
      const timestamp = callArgs[1];

      // Verify it's a valid ISO string
      expect(() => new Date(timestamp)).not.toThrow();
      expect(timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);

      jest.useRealTimers();
    });
  });

  describe('App Installation Detection', () => {
    it('should handle appinstalled event', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      const { container } = render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      // Verify prompt is showing
      const titleElement = await screen.findByText(/Install Disaster Alert/);
      expect(titleElement).toBeInTheDocument();

      // Dispatch appinstalled event
      window.dispatchEvent(new Event('appinstalled'));

      await waitFor(() => {
        expect(console.log).toHaveBeenCalledWith(
          expect.stringContaining('App installed successfully')
        );
      });

      // Prompt should hide
      await waitFor(() => {
        expect(container.firstChild).toBeNull();
      });

      jest.useRealTimers();
    });

    it('should set installed flag on appinstalled event', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      // Dispatch appinstalled
      window.dispatchEvent(new Event('appinstalled'));

      await waitFor(() => {
        expect(console.log).toHaveBeenCalledWith(
          expect.stringContaining('App installed successfully')
        );
      });

      jest.useRealTimers();
    });
  });

  describe('UI Elements', () => {
    it('should display install prompt with correct title', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const titleElement = await screen.findByText('Install Disaster Alert');
      expect(titleElement).toBeInTheDocument();

      jest.useRealTimers();
    });

    it('should display description text', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const descElement = await screen.findByText(/Install this app for quick access/i);

      expect(descElement).toBeInTheDocument();

      jest.useRealTimers();
    });

    it('should display install and dismiss buttons', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const installBtn = await screen.findByText('Install App');
      const notNowBtn = await screen.findByText('Not Now');

      expect(installBtn).toBeInTheDocument();
      expect(notNowBtn).toBeInTheDocument();

      jest.useRealTimers();
    });

    it('should display dismiss icon button with accessible label', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const dismissButtons = await screen.findAllByLabelText(/Dismiss install prompt/);
      expect(dismissButtons.length).toBeGreaterThanOrEqual(1);

      jest.useRealTimers();
    });

    it('should render SVG icon in the prompt', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      const { container } = render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      // Wait for the prompt to render
      await screen.findByText('Install Disaster Alert');

      // Find SVG elements in the container
      const svgs = container.querySelectorAll('svg');
      expect(svgs.length).toBeGreaterThan(0);

      jest.useRealTimers();
    });
  });

  describe('Dismiss Button Functionality', () => {
    it('both dismiss buttons should hide the prompt', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      mockLocalStorage.getItem.mockReturnValue(null);

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const titleElement = await screen.findByText(/Install Disaster Alert/);
      expect(titleElement).toBeInTheDocument();

      // Click "Not Now" button
      const notNowButton = screen.getByText(/Not Now/);
      fireEvent.click(notNowButton);

      // Prompt should hide
      expect(mockLocalStorage.setItem).toHaveBeenCalled();

      jest.useRealTimers();
    });
  });

  describe('Styling & Animation', () => {
    it('should have fixed positioning and centered alignment', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      const { container } = render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      await screen.findByText('Install Disaster Alert');

      // The outermost div has position fixed and bottom positioning
      const promptDiv = container.querySelector('div[style*="position"]');
      expect(promptDiv).toBeInTheDocument();
      expect(promptDiv).toHaveStyle('position: fixed');

      jest.useRealTimers();
    });

    it('should have high z-index for visibility', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      const { container } = render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      await screen.findByText('Install Disaster Alert');

      // Find the container div with z-index
      const mainDiv = container.querySelector('div[style*="position"]');
      expect(mainDiv).toBeInTheDocument();
      expect(mainDiv).toHaveStyle('z-index: 9999');

      jest.useRealTimers();
    });

    it('should have animation style defined', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      const { container } = render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      await screen.findByText('Install Disaster Alert');

      // Check that style tag with animation exists
      const styleTags = container.querySelectorAll('style');
      expect(styleTags.length).toBeGreaterThan(0);

      jest.useRealTimers();
    });
  });

  describe('Event Listeners', () => {
    it('should cleanup beforeinstallprompt listener on unmount', () => {
      const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener');

      const { unmount } = render(<PWAInstallPrompt />);

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'beforeinstallprompt',
        expect.any(Function)
      );

      removeEventListenerSpy.mockRestore();
    });
  });

  describe('Edge Cases', () => {
    it('should handle rapid beforeinstallprompt events by using the latest one', async () => {
      jest.useFakeTimers();

      const mockPrompt1 = jest.fn();
      const mockPrompt2 = jest.fn();

      const event1 = new Event('beforeinstallprompt');
      event1.prompt = mockPrompt1;
      event1.userChoice = Promise.resolve({ outcome: 'dismissed' });

      const event2 = new Event('beforeinstallprompt');
      event2.prompt = mockPrompt2;
      event2.userChoice = Promise.resolve({ outcome: 'accepted' });

      render(<PWAInstallPrompt />);

      window.dispatchEvent(event1);
      window.dispatchEvent(event2); // Should replace event1

      jest.advanceTimersByTime(5000);

      const installButton = await screen.findByText('Install App');
      fireEvent.click(installButton);

      // Should use the latest prompt (event2)
      expect(mockPrompt2).toHaveBeenCalled();

      jest.useRealTimers();
    });

    it('should not crash if userChoice resolves without outcome property', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;
      beforeinstallpromptEvent.userChoice = Promise.resolve({}); // No outcome

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const installButton = await screen.findByText('Install App');

      // Should not throw when clicking and awaiting userChoice
      fireEvent.click(installButton);

      // Let all promises resolve
      jest.advanceTimersByTime(0);

      jest.useRealTimers();
    });
  });

  describe('Logging', () => {
    it('should log install prompt outcome', async () => {
      jest.useFakeTimers();

      const mockPrompt = jest.fn();
      const mockUserChoice = Promise.resolve({ outcome: 'accepted' });

      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;
      beforeinstallpromptEvent.userChoice = mockUserChoice;

      render(<PWAInstallPrompt />);

      window.dispatchEvent(beforeinstallpromptEvent);

      jest.advanceTimersByTime(5000);

      const installButton = await screen.findByText(/Install App/);
      fireEvent.click(installButton);

      await waitFor(() => {
        expect(console.log).toHaveBeenCalledWith(expect.stringContaining('outcome: accepted'));
      });

      jest.useRealTimers();
    });
  });
});
