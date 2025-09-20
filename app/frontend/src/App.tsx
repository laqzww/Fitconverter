import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { Feature, FeatureCollection, LineString, Point } from 'geojson';
import { createAmenityMap, MapHandle } from './map';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const DEFAULT_ROUTE_ID = '11111111-1111-1111-1111-111111111111';
const CATEGORIES = ['toilet', 'water', 'cafe', 'viewpoint', 'bench'];

type Amenity = {
  id: string;
  category: string;
  props?: Record<string, unknown>;
  distance_m?: number;
  geometry: Point;
};

type SearchResponse = {
  route: {
    route_id: string;
    name: string;
    geometry: LineString;
  };
  items: Amenity[];
};

type ExportStatus = {
  status: string;
  url?: string | null;
};

function makeAmenityFeatureCollection(results: Amenity[]): FeatureCollection<Point> {
  const features: Feature<Point>[] = results.map((item) => ({
    type: 'Feature',
    properties: {
      id: item.id,
      category: item.category,
      name: (item.props && (item.props['name'] as string)) || item.category,
      distance_m: item.distance_m ?? null,
    },
    geometry: item.geometry,
  }));
  return {
    type: 'FeatureCollection',
    features,
  };
}

const formatDistance = (value?: number) => {
  if (typeof value !== 'number') return '–';
  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)} km`;
  }
  return `${Math.round(value)} m`;
};

const App: React.FC = () => {
  const mapRef = useRef<MapHandle | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([...CATEGORIES]);
  const [routeId, setRouteId] = useState<string>(DEFAULT_ROUTE_ID);
  const [routeName, setRouteName] = useState<string>('Indre By Demo Loop');
  const [radius, setRadius] = useState<number>(500);
  const [searchResults, setSearchResults] = useState<Amenity[]>([]);
  const [searching, setSearching] = useState<boolean>(false);
  const [exporting, setExporting] = useState<boolean>(false);
  const [exportStatus, setExportStatus] = useState<ExportStatus | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    mapRef.current = createAmenityMap('map', `${API_BASE}/mvt/amenities/{z}/{x}/{y}`);
    mapRef.current.setAmenityFilters(selectedCategories);
    return () => {
      mapRef.current?.map.remove();
    };
  }, []);

  useEffect(() => {
    if (mapRef.current) {
      mapRef.current.setAmenityFilters(selectedCategories);
    }
  }, [selectedCategories]);

  const handleCheckboxChange = (category: string) => {
    setSelectedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((value) => value !== category)
        : [...prev, category]
    );
  };

  const handleUpload: React.ChangeEventHandler<HTMLInputElement> = async (event) => {
    if (!event.target.files || event.target.files.length === 0) return;
    const file = event.target.files[0];
    const formData = new FormData();
    formData.append('gpx_file', file);
    formData.append('name', file.name.replace(/\.gpx$/i, ''));

    const response = await fetch(`${API_BASE}/routes`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const message = await response.text();
      alert(`Kunne ikke importere rute: ${message}`);
      return;
    }

    const json = (await response.json()) as { route_id: string };
    setRouteId(json.route_id);
    setRouteName(file.name);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const performSearch = async () => {
    setSearching(true);
    setExportStatus(null);
    try {
      const params = new URLSearchParams({
        route_id: routeId,
        radius_m: radius.toString(),
      });
      if (selectedCategories.length > 0 && selectedCategories.length < CATEGORIES.length) {
        params.set('filters', JSON.stringify(selectedCategories));
      }
      const response = await fetch(`${API_BASE}/search?${params.toString()}`);
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message);
      }
      const data = (await response.json()) as SearchResponse;
      setRouteName(data.route.name);
      setSearchResults(data.items);
      mapRef.current?.showRoute(data.route.geometry);
      mapRef.current?.showResults(makeAmenityFeatureCollection(data.items));
    } catch (error) {
      console.error('Search error', error);
      alert('Søgning mislykkedes. Se console for detaljer.');
    } finally {
      setSearching(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setExportStatus({ status: 'queued', url: null });
    try {
      const response = await fetch(`${API_BASE}/export/gpx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          route_id: routeId,
          radius_m: radius,
          filters: selectedCategories,
        }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const json = (await response.json()) as { job_id: string };
      await pollExport(json.job_id);
    } catch (error) {
      console.error('Export error', error);
      alert('Eksport mislykkedes.');
      setExporting(false);
    }
  };

  const pollExport = async (jobId: string) => {
    const poll = async (): Promise<void> => {
      const res = await fetch(`${API_BASE}/export/status/${jobId}`);
      if (!res.ok) {
        throw new Error('Status kunne ikke hentes');
      }
      const status = (await res.json()) as ExportStatus;
      setExportStatus(status);
      if (status.status === 'finished' && status.url) {
        setExporting(false);
      } else if (status.status === 'failed') {
        setExporting(false);
        alert('GPX job mislykkedes.');
      } else {
        setTimeout(poll, 1500);
      }
    };
    await poll();
  };

  const selectedSummary = useMemo(() => selectedCategories.join(', '), [selectedCategories]);

  return (
    <div className="app-shell">
      <div className="sidebar">
        <h1>Amenity Finder</h1>
        <section>
          <label htmlFor="gpx-upload">Upload GPX-rute</label>
          <input id="gpx-upload" type="file" accept=".gpx" ref={fileInputRef} onChange={handleUpload} />
          <p>
            <strong>Aktiv rute:</strong> {routeName}
            <br />
            <small>ID: {routeId}</small>
          </p>
        </section>

        <section>
          <label htmlFor="radius">Buffer-radius (meter)</label>
          <input
            id="radius"
            type="range"
            min={100}
            max={2000}
            step={50}
            value={radius}
            onChange={(event) => setRadius(Number(event.target.value))}
          />
          <div>{radius} m</div>
        </section>

        <section>
          <p>Filtrer faciliteter</p>
          {CATEGORIES.map((category) => (
            <label key={category} style={{ display: 'block', marginBottom: '0.25rem' }}>
              <input
                type="checkbox"
                checked={selectedCategories.includes(category)}
                onChange={() => handleCheckboxChange(category)}
              />{' '}
              {category}
            </label>
          ))}
          <small>Aktive: {selectedSummary || 'ingen'}</small>
        </section>

        <section>
          <button onClick={performSearch} disabled={searching}>
            {searching ? 'Søger…' : 'Find i buffer'}
          </button>
        </section>

        <section>
          <button onClick={handleExport} disabled={exporting || searchResults.length === 0}>
            {exporting ? 'Eksporterer…' : 'Eksportér GPX'}
          </button>
          {exportStatus && (
            <p>
              Status: {exportStatus.status}
              {exportStatus.url && (
                <>
                  {' '}
                  <a href={`${API_BASE}${exportStatus.url}`} target="_blank" rel="noreferrer">
                    Download GPX
                  </a>
                </>
              )}
            </p>
          )}
        </section>

        <section>
          <h2>Resultater</h2>
          <ul className="results">
            {searchResults.map((result) => (
              <li key={result.id}>
                <strong>{(result.props?.['name'] as string) || result.category}</strong>
                <span>{result.category}</span>
                <span>Afstand: {formatDistance(result.distance_m)}</span>
              </li>
            ))}
            {searchResults.length === 0 && <li>Ingen resultater endnu.</li>}
          </ul>
        </section>
      </div>
      <div className="map-container">
        <div id="map" />
      </div>
    </div>
  );
};

export default App;
