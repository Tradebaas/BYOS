import React, { useState, useEffect } from 'react';
import LevelCard from './components/LevelCard';

export default function App() {
  const [levels, setLevels] = useState([]);
  const [connected, setConnected] = useState(false);
  const [filterNoise, setFilterNoise] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.levels) {
          // Sort by ID to keep the order intuitive (newest first or oldest first)
          // Defaulting to newest first based on integer ID
          const sortedLevels = [...data.levels].sort((a, b) => parseInt(b.id) - parseInt(a.id));
          setLevels(sortedLevels);
        }
      } catch (e) {
        console.error("Failed to parse websocket message", e);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  // Filter levels based on noise toggle
  const visibleLevels = filterNoise 
    ? levels.filter(lvl => lvl.is_origin || lvl.hold_valid || lvl.has_limit) 
    : levels;

  return (
    <div className="app-container">
      <div className="header">
        <h1 style={{ marginBottom: '10px' }}>Zebas Trading Engine</h1>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '20px' }}>
          
          <div className="neu-panel-inner" style={{ display: 'flex', alignItems: 'center', fontSize: '0.9em' }}>
            <span className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}></span>
            {connected ? 'LIVE' : 'OFFLINE'}
          </div>

          <button 
            className={`neu-button ${filterNoise ? 'active' : ''}`}
            onClick={() => setFilterNoise(!filterNoise)}
          >
            {filterNoise ? 'Noise Filter: ON' : 'Noise Filter: OFF'}
          </button>
          
        </div>
      </div>

      <div className="grid-cards">
        {visibleLevels.map((level, idx) => (
          <LevelCard key={`${level.id}-${idx}`} level={level} />
        ))}
        {visibleLevels.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--text-light)', width: '100%', gridColumn: '1 / -1', marginTop: '40px' }}>
            Geen levels gevonden (of alles is gefilterd).
          </div>
        )}
      </div>
    </div>
  );
}
