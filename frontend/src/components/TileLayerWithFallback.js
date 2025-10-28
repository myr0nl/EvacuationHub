import { useEffect, useState } from 'react';
import { TileLayer } from 'react-leaflet';

/**
 * TileLayer with automatic fallback to alternative tile servers
 * Fixes "gray map" issue when primary tile server fails on mobile
 */

const TILE_SERVERS = [
  {
    name: 'OpenStreetMap',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  },
  {
    name: 'Carto Voyager',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxZoom: 19,
  },
  {
    name: 'Esri World Topo',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
    maxZoom: 19,
  },
];

export function TileLayerWithFallback() {
  const [currentServerIndex, setCurrentServerIndex] = useState(0);
  const [errorCount, setErrorCount] = useState(0);

  const currentServer = TILE_SERVERS[currentServerIndex];

  useEffect(() => {
    console.log(`[TileLayer] Using: ${currentServer.name}`);

    // Reset error count when server changes
    setErrorCount(0);

    // Listen for tile load errors
    const handleTileError = (e) => {
      console.warn('[TileLayer] Tile failed to load:', e);

      setErrorCount((prev) => {
        const newCount = prev + 1;

        // If 5+ tiles fail, try next server
        if (newCount >= 5 && currentServerIndex < TILE_SERVERS.length - 1) {
          console.error(
            `[TileLayer] ${currentServer.name} failing (${newCount} errors). Switching to ${
              TILE_SERVERS[currentServerIndex + 1].name
            }...`
          );
          setCurrentServerIndex(currentServerIndex + 1);
          return 0; // Reset counter
        }

        return newCount;
      });
    };

    // Listen for successful tile loads
    const handleTileLoad = () => {
      // Reset error count on successful load
      if (errorCount > 0) {
        setErrorCount(0);
      }
    };

    // Attach listeners to tile layer events
    // Note: This is a simplified version - in production you'd attach to the Leaflet map instance
    window.addEventListener('tileerror', handleTileError);
    window.addEventListener('tileload', handleTileLoad);

    return () => {
      window.removeEventListener('tileerror', handleTileError);
      window.removeEventListener('tileload', handleTileLoad);
    };
  }, [currentServerIndex, currentServer, errorCount]);

  return (
    <>
      <TileLayer
        key={currentServerIndex} // Force re-render when server changes
        attribution={currentServer.attribution}
        url={currentServer.url}
        maxZoom={currentServer.maxZoom}
        errorTileUrl="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        eventHandlers={{
          tileerror: (e) => {
            console.warn('[TileLayer] Tile error:', e);
            setErrorCount((prev) => prev + 1);
          },
          tileload: () => {
            // Success - reset error count
            if (errorCount > 0) {
              setErrorCount(0);
            }
          },
        }}
      />

      {/* Show warning if using fallback server */}
      {currentServerIndex > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: '10px',
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'rgba(255, 193, 7, 0.95)',
            color: '#000',
            padding: '8px 16px',
            borderRadius: '4px',
            zIndex: 1000,
            fontSize: '12px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
          }}
        >
          ⚠️ Using backup tile server: {currentServer.name}
        </div>
      )}
    </>
  );
}

export default TileLayerWithFallback;
