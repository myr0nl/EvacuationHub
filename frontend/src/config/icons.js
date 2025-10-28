// Centralized icon configuration using Lucide React
import {
  // Core UI
  Search, FileText, ShieldCheck, Settings, User, LogOut, X,

  // Disasters
  Flame, Waves, Wind, CloudRain, Mountain, Droplets, AlertTriangle, Home,

  // Alerts
  Bell, AlertCircle, Siren,

  // Map
  Map, MapPin, Navigation, Eye, EyeOff, ZoomIn, ZoomOut, Globe,

  // Facilities
  Building2, Cross, Phone, Shield,

  // Data Sources
  Satellite, Thermometer,

  // Actions
  Trash2, Zap, Check, ChevronDown, ChevronUp, Menu, RotateCcw, TestTube,

  // Navigation
  ArrowLeft, ArrowRight, ArrowUp, ArrowUpLeft, ArrowUpRight, RotateCcw as Uturn,

  // Routing
  Clock, Route, CircleDot
} from 'lucide-react';

// Disaster Type Icon Mapping
export const DISASTER_ICONS = {
  earthquake: Home,
  wildfire: Flame,
  flood: Waves,
  hurricane: CloudRain,
  tornado: Wind,
  volcano: Mountain,
  drought: Droplets,
  other: AlertTriangle,
  fire: Flame // Alias for wildfire
};

// Source Icon Mapping
export const SOURCE_ICONS = {
  nasa_firms: Satellite,
  noaa: Thermometer,
  noaa_weather: Thermometer,
  fema: Building2,
  usgs: Globe,
  cal_fire: Flame,
  cal_oes: Siren,
  user_report: User
};

// Severity Icon Mapping
export const SEVERITY_ICONS = {
  critical: AlertCircle,
  high: AlertTriangle,
  medium: AlertTriangle,
  low: AlertCircle
};

// Facility Type Icon Mapping
export const FACILITY_ICONS = {
  evacuation_center: Building2,
  hospital: Cross,
  shelter: Home,
  fire_station: Flame,
  police_station: Shield
};

// Core UI Icons
export const UI_ICONS = {
  // Brand
  logo: Search,

  // Actions
  report: FileText,
  route: ShieldCheck,
  settings: Settings,
  close: X,
  delete: Trash2,
  menu: Menu,

  // User
  user: User,
  logout: LogOut,

  // Alerts
  bell: Bell,
  alert: AlertCircle,
  warning: AlertTriangle,

  // Map
  map: Map,
  mapPin: MapPin,
  navigation: Navigation,
  eye: Eye,
  eyeOff: EyeOff,
  zoomIn: ZoomIn,
  zoomOut: ZoomOut,

  // Misc
  phone: Phone,
  check: Check,
  chevronDown: ChevronDown,
  chevronUp: ChevronUp,
  fastest: Zap,
  safest: ShieldCheck,
  clock: Clock,
  distance: Route,

  // Navigation
  arrowLeft: ArrowLeft,
  arrowRight: ArrowRight,
  arrowUp: ArrowUp,
  arrowUpLeft: ArrowUpLeft,
  arrowUpRight: ArrowUpRight,
  uturn: Uturn,
  roundabout: CircleDot
};

// Helper function to get disaster icon component
export const getDisasterIcon = (type) => {
  if (!type) return DISASTER_ICONS.other;
  const normalizedType = type.toLowerCase();
  return DISASTER_ICONS[normalizedType] || DISASTER_ICONS.other;
};

// Helper function to get source icon component
export const getSourceIcon = (source) => {
  if (!source) return SOURCE_ICONS.user_report;
  const normalizedSource = source.toLowerCase();
  return SOURCE_ICONS[normalizedSource] || SOURCE_ICONS.user_report;
};
