import maplibregl, { Map, LngLatBoundsLike } from 'maplibre-gl';
import type { FeatureCollection, LineString, Point } from 'geojson';

export type MapHandle = {
  map: Map;
  setAmenityFilters: (categories: string[]) => void;
  showRoute: (geometry: LineString | null) => void;
  showResults: (features: FeatureCollection<Point>) => void;
};

const EMPTY_LINE: FeatureCollection<LineString> = {
  type: 'FeatureCollection',
  features: [],
};

const EMPTY_POINTS: FeatureCollection<Point> = {
  type: 'FeatureCollection',
  features: [],
};

export function createAmenityMap(containerId: string, tileUrl: string): MapHandle {
  const map = new maplibregl.Map({
    container: containerId,
    style: {
      version: 8,
      sources: {
        amenities: {
          type: 'vector',
          tiles: [tileUrl],
          minzoom: 5,
          maxzoom: 15,
        },
        route: {
          type: 'geojson',
          data: EMPTY_LINE,
        },
        results: {
          type: 'geojson',
          data: EMPTY_POINTS,
        },
      },
      layers: [
        {
          id: 'background',
          type: 'background',
          paint: {
            'background-color': '#f8fafc',
          },
        },
        {
          id: 'amenities-fill',
          type: 'circle',
          source: 'amenities',
          'source-layer': 'amenities',
          paint: {
            'circle-radius': 6,
            'circle-color': '#f59e0b',
            'circle-stroke-width': 1,
            'circle-stroke-color': '#1e293b',
          },
        },
        {
          id: 'route-line',
          type: 'line',
          source: 'route',
          paint: {
            'line-color': '#2563eb',
            'line-width': 4,
          },
        },
        {
          id: 'result-points',
          type: 'circle',
          source: 'results',
          paint: {
            'circle-radius': 8,
            'circle-color': '#ef4444',
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff',
          },
        },
      ],
    },
    center: [12.576, 55.678],
    zoom: 13,
  });

  const setAmenityFilters = (categories: string[]) => {
    if (categories.length === 0) {
      map.setFilter('amenities-fill', null);
      return;
    }
    map.setFilter('amenities-fill', ['match', ['get', 'category'], categories, true, false]);
  };

  const showRoute = (geometry: LineString | null) => {
    const source = map.getSource('route') as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    if (!geometry) {
      source.setData(EMPTY_LINE);
      return;
    }
    const feature: FeatureCollection<LineString> = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry,
          properties: {},
        },
      ],
    };
    source.setData(feature);
    if (geometry.coordinates.length > 1) {
      const bounds = new maplibregl.LngLatBounds();
      geometry.coordinates.forEach(([lng, lat]) => bounds.extend([lng, lat]));
      map.fitBounds(bounds as LngLatBoundsLike, { padding: 40, maxZoom: 15 });
    }
  };

  const showResults = (features: FeatureCollection<Point>) => {
    const source = map.getSource('results') as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    source.setData(features);
  };

  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');

  return {
    map,
    setAmenityFilters,
    showRoute,
    showResults,
  };
}
