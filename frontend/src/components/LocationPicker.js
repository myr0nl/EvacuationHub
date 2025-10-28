import { useEffect } from 'react';
import { useMap, useMapEvents, Marker } from 'react-leaflet';
import L from 'leaflet';

/**
 * Component that enables clicking on the map to set a custom location.
 * Shows a simple marker at the clicked location.
 */
function LocationPicker({ enabled, onLocationSet, pickedLocation }) {
  const map = useMap();

  // Change cursor when enabled
  useEffect(() => {
    if (map) {
      const container = map.getContainer();
      if (enabled) {
        container.style.cursor = 'crosshair';
      } else {
        container.style.cursor = '';
      }
    }
  }, [enabled, map]);

  useMapEvents({
    click(e) {
      if (enabled) {
        const { lat, lng } = e.latlng;
        console.log(`Location picker: Set location to ${lat}, ${lng}`);

        // Notify parent component
        onLocationSet({
          lat: lat,
          lon: lng
        });
      }
    },
  });

  // Red circle marker (same size as user location marker: 20px with 3px border)
  const pickedLocationIcon = L.divIcon({
    className: 'picked-location-marker',
    html: `
      <div style="
        width: 20px;
        height: 20px;
        background: #dc3545;
        border: 3px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
      "></div>
    `,
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  });

  return (
    <>
      {pickedLocation && (
        <Marker position={[pickedLocation.lat, pickedLocation.lon]} icon={pickedLocationIcon} />
      )}
    </>
  );
}

export default LocationPicker;
