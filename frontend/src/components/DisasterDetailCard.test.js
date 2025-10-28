/**
 * DisasterDetailCard Component Tests
 *
 * Basic test suite for the DisasterDetailCard component.
 * Run with: npm test DisasterDetailCard.test.js
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DisasterDetailCard from './DisasterDetailCard';

// Mock disaster data
const mockDisaster = {
  id: 'test_001',
  source: 'user_report_authenticated',
  type: 'wildfire',
  latitude: 37.7749,
  longitude: -122.4194,
  severity: 'high',
  timestamp: new Date().toISOString(),
  location_name: 'San Francisco, CA',
  description: 'Test wildfire description',
  confidence_score: 0.87,
  confidence_level: 'High',
  user_display_name: 'Test User',
  user_credibility_level: 'Trusted',
  user_credibility_score: 75
};

const mockCurrentUser = {
  uid: 'user123',
  displayName: 'Test User'
};

describe('DisasterDetailCard Component', () => {
  // Test 1: Component renders without crashing
  test('renders without crashing', () => {
    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );
    expect(screen.getByText('WILDFIRE')).toBeInTheDocument();
  });

  // Test 2: Displays disaster location
  test('displays disaster location', () => {
    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );
    expect(screen.getByText('San Francisco, CA')).toBeInTheDocument();
  });

  // Test 3: Card expands on click
  test('expands card on header click', () => {
    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');

    // Initially collapsed - action buttons should not be visible
    expect(screen.queryByText(/Get Safe Route/)).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(header);

    // Action buttons should now be visible
    expect(screen.getByText(/Get Safe Route/)).toBeInTheDocument();
  });

  // Test 4: Get Route button callback
  test('calls onGetRoute when Get Safe Route button is clicked', () => {
    const mockGetRoute = jest.fn();

    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={mockGetRoute}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Click Get Safe Route button
    const routeButton = screen.getByText(/Get Safe Route/);
    fireEvent.click(routeButton);

    expect(mockGetRoute).toHaveBeenCalledWith(mockDisaster);
    expect(mockGetRoute).toHaveBeenCalledTimes(1);
  });

  // Test 5: Mark Addressed button callback
  test('calls onMarkAddressed when Mark as Addressed button is clicked', () => {
    const mockMarkAddressed = jest.fn();

    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={mockMarkAddressed}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Click Mark as Addressed button
    const addressedButton = screen.getByText(/Mark as Addressed/);
    fireEvent.click(addressedButton);

    expect(mockMarkAddressed).toHaveBeenCalledWith(mockDisaster);
    expect(mockMarkAddressed).toHaveBeenCalledTimes(1);
  });

  // Test 6: Share button callback
  test('calls onShare when Share button is clicked', () => {
    const mockShare = jest.fn();

    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={mockShare}
        currentUser={mockCurrentUser}
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Click Share button
    const shareButton = screen.getByText(/Share/);
    fireEvent.click(shareButton);

    expect(mockShare).toHaveBeenCalledWith(mockDisaster);
    expect(mockShare).toHaveBeenCalledTimes(1);
  });

  // Test 7: Mark Addressed disabled when no user
  test('disables Mark as Addressed button when user not logged in', () => {
    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={null} // Not logged in
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Button should show login required message
    expect(screen.getByText(/Login Required/)).toBeInTheDocument();
  });

  // Test 8: No Mark Addressed button for non-user reports
  test('does not show Mark as Addressed button for NASA FIRMS data', () => {
    const nasaDisaster = {
      ...mockDisaster,
      source: 'nasa_firms',
      brightness: 365.5,
      frp: 12.3,
      satellite: 'VIIRS'
    };

    render(
      <DisasterDetailCard
        disaster={nasaDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Mark as Addressed button should not be present
    expect(screen.queryByText(/Mark as Addressed/)).not.toBeInTheDocument();
  });

  // Test 9: Displays confidence score
  test('displays confidence score when available', () => {
    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Confidence should be displayed
    expect(screen.getByText(/High/)).toBeInTheDocument();
    expect(screen.getByText(/87%/)).toBeInTheDocument();
  });

  // Test 10: Displays severity badge
  test('displays severity badge correctly', () => {
    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Severity badge should be visible even when collapsed
    expect(screen.getAllByText('High').length).toBeGreaterThan(0);
  });

  // Test 11: Long description truncation
  test('truncates long descriptions with Read more button', () => {
    const longDescDisaster = {
      ...mockDisaster,
      description: 'A'.repeat(200) // Very long description
    };

    render(
      <DisasterDetailCard
        disaster={longDescDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Read more button should be present
    const readMoreButton = screen.getByText('Read more');
    expect(readMoreButton).toBeInTheDocument();

    // Click Read more
    fireEvent.click(readMoreButton);

    // Should now show Read less
    expect(screen.getByText('Read less')).toBeInTheDocument();
  });

  // Test 12: Time decay calculation
  test('calculates and displays time decay correctly', () => {
    const recentDisaster = {
      ...mockDisaster,
      timestamp: new Date(Date.now() - 300000).toISOString() // 5 minutes ago
    };

    render(
      <DisasterDetailCard
        disaster={recentDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Should show Fresh status
    expect(screen.getByText('Fresh')).toBeInTheDocument();
  });

  // Test 13: User credibility display
  test('displays user credibility when available', () => {
    render(
      <DisasterDetailCard
        disaster={mockDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Should display user credibility
    expect(screen.getByText(/Trusted/)).toBeInTheDocument();
  });

  // Test 14: NASA FIRMS specific fields
  test('displays NASA FIRMS specific fields', () => {
    const nasaDisaster = {
      ...mockDisaster,
      source: 'nasa_firms',
      brightness: 365.5,
      frp: 12.3,
      satellite: 'VIIRS NOAA-20',
      confidence: 'nominal'
    };

    render(
      <DisasterDetailCard
        disaster={nasaDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Expand card
    const header = screen.getByText('WILDFIRE').closest('.disaster-card-header');
    fireEvent.click(header);

    // Should display NASA-specific fields
    expect(screen.getByText(/Brightness:/)).toBeInTheDocument();
    expect(screen.getByText(/365.5K/)).toBeInTheDocument();
    expect(screen.getByText(/Fire Radiative Power:/)).toBeInTheDocument();
    expect(screen.getByText(/12.3 MW/)).toBeInTheDocument();
  });

  // Test 15: Handles missing optional fields gracefully
  test('handles missing optional fields gracefully', () => {
    const minimalDisaster = {
      id: 'test_002',
      source: 'user_report',
      type: 'flood',
      latitude: 40.7128,
      longitude: -74.0060,
      severity: 'medium',
      timestamp: new Date().toISOString()
      // No location_name, description, etc.
    };

    render(
      <DisasterDetailCard
        disaster={minimalDisaster}
        onGetRoute={() => {}}
        onMarkAddressed={() => {}}
        onShare={() => {}}
        currentUser={mockCurrentUser}
      />
    );

    // Should render without crashing
    expect(screen.getByText('FLOOD')).toBeInTheDocument();

    // Should display coordinates as fallback
    expect(screen.getByText(/40.7128, -74.0060/)).toBeInTheDocument();
  });
});
