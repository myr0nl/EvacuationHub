# Evacuation Hub

<div align="center">

![Version](https://img.shields.io/badge/version-1.1.67-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![React](https://img.shields.io/badge/react-19.2.0-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-blue.svg)

**See the full scope of disasters. Navigate to safety.**

A real-time disaster tracking and navigation platform combining crowdsourced reports with 8 trusted official data sources to help users monitor, assess, and evacuate during emergencies.

[Live Demo](https://ds.myrondomain.com)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Live Demo](#live-demo)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Data Sources](#data-sources)
- [Technology Stack](#technology-stack)
- [Screenshots](#screenshots)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Overview

**DisasterScope** is a comprehensive disaster alert and navigation system designed to save lives during emergencies. By integrating multiple authoritative data sources with crowdsourced intelligence, the platform provides real-time situational awareness and safe evacuation routing.


### What Makes DisasterScope Different?

- **Multi-Source Intelligence**: Combines 8 official data sources (NASA, NOAA, FEMA, USGS, GDACS, Cal Fire, Cal OES) with user reports
- **AI-Powered Confidence Scoring**: Hybrid heuristic + AI system validates report credibility in real-time
- **Proximity Alerts**: Adaptive polling system monitors disasters within 5-50 miles with graduated severity levels
- **Smart Evacuation Routing**: Access to 56,000+ HIFLD emergency shelters with disaster-aware route planning
- **Emergency-First Design**: Quick reports (location + type only) score ~78% confidence - no essays required during crises

---

## Key Features

### Real-Time Disaster Tracking
- **Interactive Leaflet Map** with clustered markers for visual clarity
- **8 Official Data Sources** continuously monitored and cached
- **Crowdsourced Reports** with automatic credibility assessment
- **US-Wide Coverage** including continental US, Alaska, Hawaii, and territories

### Proximity Alert System
- **Configurable Radius** (5-50 miles) with adaptive polling
- **Graduated Severity Levels**: Critical (5 mi), High (15 mi), Medium (30 mi), Low (50 mi)
- **Smart Filtering** by disaster type and severity preferences
- **Quiet Hours** and notification channel customization
- **Real-Time Updates** with visual radius circle on map

### AI-Enhanced Confidence Scoring
- **Three-Stage Pipeline**:
  1. Heuristic scoring (source credibility, recency, spatial validation)
  2. Spatial corroboration across all 8 data sources (50-mile radius)
  3. AI enhancement via GPT-4o-mini (rate-limited, cached)
- **Transparency**: Scores and AI reasoning visible to users
- **Emergency-Optimized**: Minimal reports score 78% - sufficient for action
- **Multi-Source Validation**: Official sources provide 1.5x corroboration weight

### Safe Zone Navigation
- **56,000+ Emergency Shelters** via HIFLD National Shelter System
- **Evacuation Centers** from Red Cross and FEMA
- **Disaster-Aware Routing** with automatic hazard avoidance buffers
- **Turn-by-Turn Directions** via HERE Maps or Google Maps integration
- **Safety Checks** for 10-mile radius threats around destinations

### Performance & Reliability
- **Smart Caching**: Firebase-based system with source-specific refresh rates
- **Graceful Degradation**: Works without AI API keys or when external APIs fail
- **Rate Limiting**: Emergency-optimized thresholds (600/hr proximity, 100/day reports)
- **Auto-Cleanup**: Removes expired alerts and old wildfire data
- **Deduplication**: Prevents duplicate entries across all sources

---

## Live Demo

**Coming Soon**: Deployment information will be added here.

For now, follow the [Quick Start](#quick-start) guide to run locally.

---

## Quick Start

### Prerequisites
- **Node.js** 18+ and npm
- **Python** 3.8+
- **Firebase** project with Realtime Database
- **NASA FIRMS API Key** (free from https://firms.modaps.eosdis.nasa.gov/api/)
- **OpenAI API Key** (optional, enables AI confidence enhancement)

### 1. Clone the Repository
```bash
git clone https://github.com/bdbb/alerter.git
cd alerter
```

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your credentials:
# - FIREBASE_CREDENTIALS_PATH (path to firebaseKey.json)
# - FIREBASE_DATABASE_URL (your Firebase database URL)
# - NASA_FIRMS_API_KEY (your NASA FIRMS API key)
# - OPENAI_API_KEY (optional, for AI enhancement)

# Run backend (port 5001)
python app.py
```

**Quick Start Script** (handles venv setup automatically):
```bash
./start-backend.sh
```

### 3. Frontend Setup
```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install

# Run frontend (port 3000)
npm start
```

**Quick Start Script**:
```bash
./start-frontend.sh
```

### 4. Verify Installation
1. Open http://localhost:3000
2. You should see the disaster map interface
3. Test report submission:
   - Click "Report Disaster" button
   - Select disaster type and severity
   - Click "Use My Location" or enter coordinates
   - Submit and verify it appears on the map

---

## Architecture

### System Overview

```
┌───────────────────────────────────────────────────────────────┐
│                         Frontend (React)                      │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │   Map    │  │ Proximity    │  │  Safe Route Panel       │  │
│  │ (Leaflet)│  │ Alerts       │  │  (Evacuation Routing)   │  │
│  └──────────┘  └──────────────┘  └─────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
                              ↕ REST API
┌────────────────────────────────────────────────────────────────┐
│                       Backend (Flask)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │             Service Layer (12 Services)                  │  │
│  │  • NASAFirmsService        • FEMADisasterService         │  │
│  │  • NOAAWeatherService      • USGSEarthquakeService       │  │
│  │  • GDACSService            • CalFireService              │  │
│  │  • CalOESService           • ConfidenceScorer            │  │
│  │  • ProximityAlertService   • SafeZoneService             │  │
│  │  • HIFLDShelterService     • RouteCalculationService     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │             Cache Manager (Smart Caching)                │  │
│  │  • Wildfires: 3h  • FEMA: 6h  • USGS: 15min              │  │
│  │  • Weather: 1h    • GDACS: 1h • Cal Fire: 30min          │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│              Firebase Realtime Database                         │
│  • /reports                    • /public_data_cache             │
│  • /user_alert_preferences     • /user_map_settings             │
│  • /geocoding_cache            • /ai_analysis_cache             │
│  • /safe_zones                 • /user_notifications            │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow: Report Submission

```
User Submits Report
    ↓
API Validation (lat/lon, type, severity, reCAPTCHA)
    ↓
Fetch Nearby Reports (50-mile radius)
    ├─ User reports
    ├─ NASA FIRMS wildfires
    ├─ NOAA weather alerts
    ├─ FEMA disasters
    ├─ USGS earthquakes
    ├─ GDACS global events
    ├─ Cal Fire incidents
    └─ Cal OES alerts
    ↓
Confidence Scoring (3 stages)
    ├─ Heuristics (always runs)
    ├─ Spatial corroboration (if nearby reports exist)
    └─ AI enhancement (rate-limited, cached)
    ↓
Reverse Geocoding (location name from coordinates)
    ↓
Retroactive Confidence Updates (nearby reports get re-scored)
    ↓
Firebase Save + Return to User
```

### Confidence Scoring Pipeline

The system uses a **three-stage hybrid approach** to assess report credibility:

1. **Heuristic Scoring** (100% weight, <1ms)
   - Source credibility (40%): Official 95%, user 50-85% based on reCAPTCHA
   - Temporal recency (20%): Gradual decay, 100% for <15min, 50% min after 24h
   - Spatial validation (20%): US coordinate validation
   - Data completeness (10%): Core fields (lat/lon/type) = 80%, bonus fields = 20%
   - Type validation (10%): Valid disaster type recognition

2. **Spatial Corroboration** (0-60% boost)
   - Queries nearby reports within 50 miles (all 8 sources)
   - Distance scoring: Exponential decay (1.0 at <6 mi → 0.2 at 30-50 mi)
   - Source weighting: Official 1.5x, user reports 1.0x
   - Multi-source bonus: 4+ different sources = +60% boost
   - Boost thresholds: ≥4.0 score = +35%, ≥3.0 = +30%, ≥2.0 = +20%

3. **AI Enhancement** (30% weight when available)
   - Rate-limited: 50 requests/hour, 24-hour cache
   - GPT-4o-mini analyzes text coherence, plausibility, specificity
   - Blending: (heuristic × 70%) + (AI × 30%)
   - Returns reasoning displayed to users

**Final Score Ranges:**
- High (80-100%): Green badge
- Medium (60-79%): Yellow badge
- Low (0-59%): Red badge

---

## Data Sources

DisasterScope integrates **8 official data sources** for comprehensive disaster monitoring:

### Displayed Sources (3)

| Source | Type | Update Frequency | Coverage | Description |
|--------|------|------------------|----------|-------------|
| **NASA FIRMS** | Wildfires | 3 hours | Global | Satellite wildfire detection via VIIRS/MODIS with brightness, FRP, and confidence metrics |
| **NOAA** | Weather Alerts | 1 hour | US | National Weather Service active alerts with severity levels (Extreme, Severe, Moderate, Minor) |
| **User Reports** | All Types | Real-time | Global | Crowdsourced disaster reports with AI-validated credibility scoring |

### Confidence Scoring & Proximity Alert Sources (5)

| Source | Type | Update Frequency | Coverage | Description |
|--------|------|------------------|----------|-------------|
| **FEMA** | Disasters | 6 hours | US | Federal disaster declarations and emergency response data |
| **USGS** | Earthquakes | 15 minutes | Global | Real-time seismic data, magnitude 2.5+ from earthquake monitoring network |
| **GDACS** | All Types | 1 hour | Global | UN-backed Global Disaster Alert and Coordination System |
| **Cal Fire** | Wildfires | 30 minutes | California | Active wildfire incidents with acres burned and containment status |
| **Cal OES** | All Types | 30 minutes | California | State emergency alerts via California Office of Emergency Services RSS |

### Emergency Shelter Data

| Source | Type | Update Frequency | Coverage | Description |
|--------|------|------------------|----------|-------------|
| **HIFLD** | Safe Zones | 6 hours | US | 56,000+ evacuation centers and emergency shelters (FEMA + Red Cross synced) |

**Total Coverage**: 8 official data sources + crowdsourced reports = 9 intelligence streams

---

## Technology Stack

### Frontend
- **Framework**: React 19.2.0 with React Router
- **Mapping**: Leaflet 1.9.4 + react-leaflet 5.0.0
- **Clustering**: leaflet.markercluster for performance
- **UI Components**: Lucide React icons, Radix UI primitives
- **Styling**: TailwindCSS with custom animations
- **HTTP Client**: Axios 1.12.2
- **Authentication**: Firebase Auth (Google, email/password, anonymous)
- **Analytics**: Vercel Analytics + Speed Insights

### Backend
- **Framework**: Flask 3.0.0 (Python 3.8+)
- **Database**: Firebase Realtime Database
- **Authentication**: Firebase Admin SDK
- **Rate Limiting**: Flask-Limiter (IP-based)
- **AI Integration**: OpenAI GPT-4o-mini
- **Geocoding**: OpenStreetMap Nominatim
- **Routing**: HERE Maps + Google Maps APIs
- **Geometry**: Shapely 2.0.6 for polygon calculations
- **HTTP Client**: Requests 2.31.0

### Infrastructure
- **Database**: Firebase Realtime Database (NoSQL)
- **Caching**: Firebase-based with automatic cleanup
- **Deployment**: Vercel (frontend) + Cloud hosting (backend)
- **Version Control**: Git with automated semantic versioning

### External APIs
- NASA FIRMS API (wildfire data)
- NOAA Weather API (weather alerts)
- FEMA API (disaster declarations)
- USGS Earthquake API (seismic data)
- GDACS API (global disasters)
- Cal Fire API (California wildfires)
- Cal OES RSS (California alerts)
- HIFLD ArcGIS REST API (emergency shelters)
- OpenStreetMap Nominatim (reverse geocoding)
- HERE Maps Routing API (turn-by-turn directions)
- Google Maps Directions API (alternative routing)

---

## Screenshots

### Interactive Disaster Map
The main interface displays disasters from all sources with color-coded markers:
- **Blue circles**: User-submitted reports
- **Orange circles**: NASA FIRMS wildfires (brightness-based sizing)
- **Colored squares**: NOAA weather alerts (severity-based colors)
- **Marker clustering**: Automatic grouping for performance at high zoom levels

### Proximity Alert Panel
Real-time notification panel showing nearby disasters:
- **Bell icon with badge**: Active alert count
- **Distance indicators**: Miles from user location
- **Severity badges**: Critical (red), High (orange), Medium (yellow), Low (blue)
- **Source attribution**: NASA FIRMS, NOAA, User Report, etc.
- **Actions**: View on map, acknowledge, dismiss all

### Confidence Scoring Display
User report popups show AI-enhanced credibility assessment:
- **Confidence badge**: Green (High), Yellow (Medium), Red (Low)
- **Percentage score**: 0-100% credibility rating
- **AI reasoning**: "Clear description of shaking buildings, plausible earthquake report"
- **Timestamp**: Time since report submission
- **Location**: Reverse-geocoded city/state

### Safe Route Panel
Evacuation routing interface:
- **Destination search**: Find nearby shelters (up to 56,000 HIFLD facilities)
- **Route visualization**: Color-coded path with disaster avoidance zones
- **Turn-by-turn directions**: HERE Maps or Google Maps integration
- **Safety indicators**: 10-mile threat radius around shelters
- **Route metrics**: Distance, estimated travel time, disaster count avoided

### Alert Settings Modal
User preferences configuration:
- **Radius slider**: 5-50 miles proximity monitoring
- **Severity filters**: Critical, High, Medium, Low toggles
- **Disaster type filters**: Earthquake, flood, wildfire, hurricane, tornado, volcano, drought
- **Notification channels**: In-app, push, email, SMS (future features)
- **Quiet hours**: Start/end time configuration
- **Visual radius circle**: Toggle map overlay

---

## API Documentation

### Base URL
```
http://localhost:5001/api
```

### Core Endpoints

#### Health Check
```http
GET /api/health
```
Returns service status and version information.

#### Disaster Reports
```http
GET /api/reports
```
Fetch all user-submitted reports with confidence scores.

```http
POST /api/reports
Content-Type: application/json

{
  "latitude": 37.7749,
  "longitude": -122.4194,
  "type": "earthquake",
  "severity": "high",
  "description": "Strong shaking felt in downtown area",
  "recaptcha_score": 0.8,
  "id_token": "optional-firebase-auth-token"
}
```
Submit a new disaster report. Returns confidence score and reasoning.

```http
DELETE /api/reports/{report_id}
Authorization: Bearer {firebase_id_token}
```
Delete a report (requires ownership or admin privileges).

#### Public Data
```http
GET /api/public-data/wildfires?days=1
```
NASA FIRMS wildfire data (cached 3 hours).

```http
GET /api/public-data/weather-alerts?severity=Severe
```
NOAA weather alerts (cached 1 hour).

```http
GET /api/public-data/all?days=1&severity=Minor
```
Combined data from NASA FIRMS + NOAA.

#### Proximity Alerts
```http
GET /api/alerts/proximity?lat={lat}&lon={lon}&radius={radius}
Authorization: Bearer {firebase_id_token} (optional)
```
Check nearby disasters within specified radius (5-50 miles).
- Rate limit: 600 requests/hour
- Returns: `{alerts: [], highest_severity: 'high', count: 5, closest_distance: 3.2}`

```http
GET /api/alerts/preferences
Authorization: Bearer {firebase_id_token}
```
Get user alert preferences.

```http
PUT /api/alerts/preferences
Authorization: Bearer {firebase_id_token}
Content-Type: application/json

{
  "enabled": true,
  "show_radius_circle": true,
  "severity_filter": ["critical", "high", "medium"],
  "disaster_types": ["earthquake", "wildfire", "flood"],
  "quiet_hours": {"enabled": true, "start": "22:00", "end": "08:00"}
}
```
Update alert preferences.

#### Safe Zones
```http
GET /api/safe-zones/nearest?lat={lat}&lon={lon}&limit=10
```
Find nearest evacuation centers (HIFLD shelters + manual zones).

```http
POST /api/safe-zones/route
Content-Type: application/json

{
  "start_lat": 37.7749,
  "start_lon": -122.4194,
  "end_lat": 37.8044,
  "end_lon": -122.2712,
  "routing_provider": "here"
}
```
Calculate disaster-aware evacuation route.

#### Cache Management
```http
GET /api/cache/status
```
View cache metadata and last update times.

```http
POST /api/cache/clear
Content-Type: application/json

{
  "type": "wildfires"  // optional: "weather_alerts", "fema_disasters", etc.
}
```
Clear cache (admin endpoint).

```http
POST /api/cache/refresh
```
Force refresh from external APIs.

### Rate Limits

| Endpoint | Limit | Notes |
|----------|-------|-------|
| Proximity alerts | 600/hour | Supports adaptive polling (10/min) |
| Report submission | 20/hour, 100/day | Burst reporting during emergencies |
| Safe zones | 200/hour | Evacuation planning |
| Route calculation | 40/hour, 10/min | Recalculation when disasters change |
| Authentication | 5/15min, 20/day | Brute force protection |

---

## Development

### Project Structure
```
alerter/
├── backend/
│   ├── app.py                    # Flask application entry point
│   ├── services/                 # Business logic layer (12 services)
│   │   ├── nasa_firms.py         # NASA FIRMS wildfire data
│   │   ├── noaa_weather.py       # NOAA weather alerts
│   │   ├── fema_disaster_service.py
│   │   ├── usgs_earthquake_service.py
│   │   ├── gdacs_service.py
│   │   ├── cal_fire_service.py
│   │   ├── cal_oes_service.py
│   │   ├── confidence_scorer.py  # AI + heuristic scoring
│   │   ├── proximity_alert_service.py
│   │   ├── safe_zone_service.py
│   │   ├── hifld_shelter_service.py
│   │   └── route_calculation_service.py
│   ├── utils/                    # Helper functions
│   │   ├── geo.py                # Haversine distance calculations
│   │   └── validators.py         # Input validation
│   ├── tests/                    # Backend unit tests
│   │   ├── test_confidence_scorer.py
│   │   ├── test_proximity_alerts.py
│   │   └── test_hifld_shelter_service.py
│   └── requirements.txt          # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map.js            # Leaflet map with clustering
│   │   │   ├── DisasterSidebar.js
│   │   │   ├── ReportForm.js
│   │   │   ├── AlertNotificationPanel.js
│   │   │   ├── AlertSettingsModal.js
│   │   │   ├── ProximityRangeControl.js
│   │   │   └── SafeRoutePanel.js
│   │   ├── App.js                # React application entry point
│   │   └── firebase.js           # Firebase configuration
│   ├── public/
│   │   └── version.json          # Automated semantic versioning
│   ├── package.json              # Node dependencies
│   └── tests/                    # E2E Playwright tests
├── README.md                     # This file
├── .git/hooks/pre-commit         # Auto-increment version on commit
├── start-backend.sh              # Backend quick start script
└── start-frontend.sh             # Frontend quick start script
```

### Running Tests

#### Backend Tests (pytest)
```bash
cd backend
source venv/bin/activate

# Run all tests
pytest

# Run specific test file
pytest tests/test_confidence_scorer.py -v

# Run single test function
pytest tests/test_confidence_scorer.py::test_minimal_emergency_report -v

# Run tests matching keyword
pytest -k "confidence" -v
```

#### E2E Tests (Playwright)
```bash
cd frontend

# Run all E2E tests
npm run test:e2e

# Run with UI mode
npm run test:e2e:ui

# Run in headed mode (see browser)
npm run test:e2e:headed
```

Test coverage:
- Data loading from 8 sources
- Sidebar filter interactions
- Map marker clustering and popups
- Proximity alert panel functionality
- Settings modal validation
- localStorage persistence
- Console error monitoring

### Adding New Features

#### Add New Disaster Type
1. Update `valid_types` in `backend/app.py` and `confidence_scorer.py`
2. Add color mapping in `frontend/src/components/Map.js` MARKER_COLORS
3. Add to DisasterSidebar.js filter options

#### Modify Confidence Scoring
Edit `_calculate_heuristic_score()` in `backend/services/confidence_scorer.py`
- Weights must sum to 1.0
- Current: source (0.4) + recency (0.2) + spatial (0.2) + completeness (0.1) + type (0.1)

#### Adjust Cache Expiration
Modify `CacheManager.CACHE_DURATIONS` in `backend/services/cache_manager.py`

#### Customize Proximity Alert Behavior
- Polling intervals: Edit `POLLING_INTERVALS` in `frontend/src/App.js`
- Radius limits: Edit validation in `backend/services/proximity_alert_service.py`
- Severity thresholds: Edit `_calculate_severity_level()`

### Environment Variables

#### Backend (.env)
```bash
# Required
FIREBASE_CREDENTIALS_PATH=path/to/firebaseKey.json
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
NASA_FIRMS_API_KEY=your-nasa-api-key

# Optional
OPENAI_API_KEY=sk-...                # Enables AI confidence enhancement
FLASK_ENV=development                # production | development
FRONTEND_URL=http://localhost:3000   # CORS configuration
HERE_API_KEY=your-here-api-key       # Route calculation
GOOGLE_MAPS_API_KEY=your-google-key  # Alternative routing
```

#### Frontend (.env)
```bash
REACT_APP_API_URL=http://localhost:5001  # Backend URL
```

### Versioning System

The project uses **automated semantic versioning** (MAJOR.MINOR.PATCH):
- **Patch**: Auto-increments on every commit via Git pre-commit hook
- **Minor**: Manual increment for new features
- **Major**: Manual increment for breaking changes

Version displayed in footer: `v1.1.67`

**Pre-commit hook** (`.git/hooks/pre-commit`):
- Python-based for reliable JSON parsing
- Updates `frontend/public/version.json`
- Captures Git commit hash and build timestamp

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** with clear commit messages
4. **Write tests** for new features
5. **Run tests** (`pytest` for backend, `npm run test:e2e` for frontend)
6. **Commit your changes** (version auto-increments via pre-commit hook)
7. **Push to the branch** (`git push origin feature/amazing-feature`)
8. **Open a Pull Request**

### Development Priorities
- Confidence scoring algorithm improvements
- Additional data source integrations
- Mobile app development (React Native)
- Enhanced fraud detection patterns
- Real-time push notifications
- Advanced analytics dashboard

### Code Style
- **Python**: PEP 8 (black formatter recommended)
- **JavaScript**: ESLint with React configuration
- **Commits**: Conventional Commits format preferred

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

### Data Providers
- **NASA FIRMS** - Fire Information for Resource Management System
  - Website: https://firms.modaps.eosdis.nasa.gov/
  - Data: VIIRS/MODIS satellite wildfire detection
- **NOAA** - National Oceanic and Atmospheric Administration
  - Website: https://www.weather.gov/
  - Data: National Weather Service active alerts
- **FEMA** - Federal Emergency Management Agency
  - Website: https://www.fema.gov/
  - Data: Disaster declarations and emergency response
- **USGS** - United States Geological Survey
  - Website: https://www.usgs.gov/
  - Data: Real-time earthquake monitoring
- **GDACS** - Global Disaster Alert and Coordination System
  - Website: https://www.gdacs.org/
  - Data: UN-backed global disaster coordination
- **Cal Fire** - California Department of Forestry and Fire Protection
  - Website: https://www.fire.ca.gov/
  - Data: Active wildfire incidents
- **Cal OES** - California Office of Emergency Services
  - Website: https://www.caloes.ca.gov/
  - Data: State emergency alerts
- **HIFLD** - Homeland Infrastructure Foundation-Level Data
  - Website: https://hifld-geoplatform.opendata.arcgis.com/
  - Data: 56,000+ emergency shelters and evacuation centers

### Technologies
- **OpenAI** - GPT-4o-mini for AI confidence enhancement
- **Firebase** - Realtime Database and Authentication
- **Leaflet** - Open-source mapping library
- **React** - UI framework
- **Flask** - Python web framework
- **HERE Maps** - Routing and geocoding services
- **Google Maps** - Alternative routing provider
- **OpenStreetMap** - Reverse geocoding data

### Inspiration
Built to help communities respond effectively to disasters through real-time intelligence, validated reporting, and safe evacuation guidance.

---

<div align="center">

**DisasterScope** - See the full scope of disasters. Navigate to safety.

[GitHub](https://github.com/myr0nl/EvacuationHub)

Made for emergency response and community safety

</div>
