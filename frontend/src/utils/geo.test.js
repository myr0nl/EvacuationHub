/**
 * Unit tests for geospatial utility functions
 * Tests coordinate validation, distance calculations, and edge cases
 */

import {
  isValidCoordinates,
  normalizeLongitude,
  calculateDistance,
  isWithinRadius
} from './geo';

describe('isValidCoordinates', () => {
  describe('Valid coordinates', () => {
    test('should accept valid US coordinates (San Francisco)', () => {
      expect(isValidCoordinates(37.7749, -122.4194)).toBe(true);
    });

    test('should accept equator at prime meridian (Gulf of Guinea)', () => {
      expect(isValidCoordinates(0, 0)).toBe(true);
    });

    test('should accept equator in Pacific', () => {
      expect(isValidCoordinates(0, -122.4194)).toBe(true);
    });

    test('should accept prime meridian in Algeria', () => {
      expect(isValidCoordinates(37.7749, 0)).toBe(true);
    });

    test('should accept North Pole', () => {
      expect(isValidCoordinates(90, 0)).toBe(true);
    });

    test('should accept South Pole', () => {
      expect(isValidCoordinates(-90, 0)).toBe(true);
    });

    test('should accept International Date Line (west)', () => {
      expect(isValidCoordinates(40, -180)).toBe(true);
    });

    test('should accept International Date Line (east)', () => {
      expect(isValidCoordinates(40, 180)).toBe(true);
    });

    test('should accept negative coordinates (southern hemisphere, eastern hemisphere)', () => {
      expect(isValidCoordinates(-33.8688, 151.2093)).toBe(true); // Sydney
    });
  });

  describe('Invalid coordinates', () => {
    test('should reject latitude > 90', () => {
      expect(isValidCoordinates(91, 0)).toBe(false);
    });

    test('should reject latitude < -90', () => {
      expect(isValidCoordinates(-91, 0)).toBe(false);
    });

    test('should reject longitude > 180', () => {
      expect(isValidCoordinates(0, 181)).toBe(false);
    });

    test('should reject longitude < -180', () => {
      expect(isValidCoordinates(0, -181)).toBe(false);
    });

    test('should reject null latitude', () => {
      expect(isValidCoordinates(null, 0)).toBe(false);
    });

    test('should reject null longitude', () => {
      expect(isValidCoordinates(0, null)).toBe(false);
    });

    test('should reject undefined latitude', () => {
      expect(isValidCoordinates(undefined, 0)).toBe(false);
    });

    test('should reject undefined longitude', () => {
      expect(isValidCoordinates(0, undefined)).toBe(false);
    });

    test('should reject NaN latitude', () => {
      expect(isValidCoordinates(NaN, 0)).toBe(false);
    });

    test('should reject NaN longitude', () => {
      expect(isValidCoordinates(0, NaN)).toBe(false);
    });

    test('should reject Infinity latitude', () => {
      expect(isValidCoordinates(Infinity, 0)).toBe(false);
    });

    test('should reject Infinity longitude', () => {
      expect(isValidCoordinates(0, Infinity)).toBe(false);
    });

    test('should reject string latitude', () => {
      expect(isValidCoordinates("37.7749", 0)).toBe(false);
    });

    test('should reject string longitude', () => {
      expect(isValidCoordinates(0, "-122.4194")).toBe(false);
    });
  });
});

describe('normalizeLongitude', () => {
  test('should normalize 181 to -179', () => {
    expect(normalizeLongitude(181)).toBeCloseTo(-179, 5);
  });

  test('should normalize -181 to 179', () => {
    expect(normalizeLongitude(-181)).toBeCloseTo(179, 5);
  });

  test('should normalize 360 to 0', () => {
    expect(normalizeLongitude(360)).toBeCloseTo(0, 5);
  });

  test('should leave 0 (prime meridian) unchanged', () => {
    expect(normalizeLongitude(0)).toBeCloseTo(0, 5);
  });

  test('should leave valid longitude (-180 to 180) unchanged', () => {
    expect(normalizeLongitude(-122.4194)).toBeCloseTo(-122.4194, 5);
  });

  test('should normalize 540 to 180', () => {
    expect(normalizeLongitude(540)).toBeCloseTo(180, 5);
  });

  test('should normalize -540 to -180', () => {
    expect(normalizeLongitude(-540)).toBeCloseTo(-180, 5);
  });
});

describe('calculateDistance', () => {
  describe('Known distances', () => {
    test('should calculate SF to LA distance (~347 miles)', () => {
      const distance = calculateDistance(
        37.7749, -122.4194,  // San Francisco
        34.0522, -118.2437   // Los Angeles
      );
      expect(distance).toBeGreaterThan(340);
      expect(distance).toBeLessThan(355);
    });

    test('should calculate NYC to Boston distance (~190 miles)', () => {
      const distance = calculateDistance(
        40.7128, -74.0060,   // New York
        42.3601, -71.0589    // Boston
      );
      expect(distance).toBeGreaterThan(185);
      expect(distance).toBeLessThan(195);
    });

    test('should return 0 for same point', () => {
      const distance = calculateDistance(
        37.7749, -122.4194,
        37.7749, -122.4194
      );
      expect(distance).toBeCloseTo(0, 5);
    });

    test('should calculate 1 degree longitude at equator (~69 miles)', () => {
      const distance = calculateDistance(0, 0, 0, 1);
      expect(distance).toBeGreaterThan(68);
      expect(distance).toBeLessThan(70);
    });
  });

  describe('Edge cases', () => {
    test('should handle equator crossing', () => {
      const distance = calculateDistance(
        -1, 0,  // 1° south of equator
        1, 0    // 1° north of equator
      );
      expect(distance).toBeGreaterThan(130);
      expect(distance).toBeLessThan(140);
    });

    test('should handle prime meridian crossing', () => {
      const distance = calculateDistance(
        40, -1,  // 1° west of prime meridian
        40, 1    // 1° east of prime meridian
      );
      expect(distance).toBeGreaterThan(100);
      expect(distance).toBeLessThan(110);
    });

    test('should handle International Date Line crossing', () => {
      const distance = calculateDistance(
        40, 179,   // Near IDL east
        40, -179   // Near IDL west
      );
      // These are only 2° apart, not 358° apart (~106 miles at 40°N)
      expect(distance).toBeGreaterThan(100);
      expect(distance).toBeLessThan(110);
    });

    test('should handle pole to pole distance', () => {
      const distance = calculateDistance(
        90, 0,    // North Pole
        -90, 0    // South Pole
      );
      // Half Earth's circumference ~12,450 miles
      expect(distance).toBeGreaterThan(12400);
      expect(distance).toBeLessThan(12500);
    });
  });

  describe('Invalid coordinates', () => {
    test('should throw error for invalid first latitude', () => {
      expect(() => {
        calculateDistance(91, 0, 40, -74);
      }).toThrow('Invalid first coordinate');
    });

    test('should throw error for invalid first longitude', () => {
      expect(() => {
        calculateDistance(40, 181, 40, -74);
      }).toThrow('Invalid first coordinate');
    });

    test('should throw error for invalid second latitude', () => {
      expect(() => {
        calculateDistance(40, -74, -91, 0);
      }).toThrow('Invalid second coordinate');
    });

    test('should throw error for invalid second longitude', () => {
      expect(() => {
        calculateDistance(40, -74, 40, -181);
      }).toThrow('Invalid second coordinate');
    });

    test('should throw error for NaN coordinates', () => {
      expect(() => {
        calculateDistance(NaN, 0, 40, -74);
      }).toThrow();
    });
  });
});

describe('isWithinRadius', () => {
  test('should return true for points within radius', () => {
    // SF City Hall to Golden Gate Bridge (~4.5 miles)
    const result = isWithinRadius(
      37.7793, -122.4193,  // City Hall
      37.8199, -122.4783,  // Golden Gate Bridge
      5  // 5 mile radius
    );
    expect(result).toBe(true);
  });

  test('should return false for points outside radius', () => {
    // SF to LA (~347 miles)
    const result = isWithinRadius(
      37.7749, -122.4194,  // San Francisco
      34.0522, -118.2437,  // Los Angeles
      100  // 100 mile radius
    );
    expect(result).toBe(false);
  });

  test('should return true for exact boundary', () => {
    // Create two points exactly 5 miles apart
    const result = isWithinRadius(
      37.7749, -122.4194,
      37.7749, -122.3472,  // ~5 miles east
      5  // 5 mile radius
    );
    expect(result).toBe(true);
  });

  test('should return true for same point (0 distance)', () => {
    const result = isWithinRadius(
      37.7749, -122.4194,
      37.7749, -122.4194,
      5
    );
    expect(result).toBe(true);
  });

  test('should handle equator crossing', () => {
    const result = isWithinRadius(
      -1, 0,  // 1° south
      1, 0,   // 1° north
      200     // 200 mile radius
    );
    expect(result).toBe(true);
  });
});
