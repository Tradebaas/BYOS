import React from 'react';

export default function LevelCard({ level }) {
  // Extract main traits from level object coming from WebSocket
  const { 
    id, price, type, test_count, is_origin, is_active,
    hold_valid, has_limit, hold_price, timestamp
  } = level;

  // Add opacity for historical levels
  const cardOpacity = is_active ? 1.0 : 0.5;

  return (
    <div className="neu-panel" style={{ display: 'flex', flexDirection: 'column', gap: '15px', opacity: cardOpacity }}>
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, color: type === 'RESISTANCE' ? '#e74c3c' : '#2ecc71', display: 'flex', gap: '8px', alignItems: 'center' }}>
          {type}
          {is_origin && <span style={{ fontSize: '0.6em', padding: '2px 6px', background: 'var(--accent)', color: 'white', borderRadius: '4px' }}>ORIGIN</span>}
          {!is_active && <span style={{ fontSize: '0.6em', padding: '2px 6px', background: '#95a5a6', color: 'white', borderRadius: '4px' }}>HISTORICAL</span>}
        </h3>
        <span className="neu-panel-inner" style={{ fontSize: '0.85em', color: 'var(--text-light)' }}>
          ID: {id}
        </span>
      </div>

      {/* Main Prices */}
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: '0.85em', color: 'var(--text-light)' }}>Break Price</span>
          <span style={{ fontSize: '1.4em', fontWeight: 'bold' }}>{parseFloat(price).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</span>
        </div>
        
        {hold_valid && hold_price && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
            <span style={{ fontSize: '0.85em', color: 'var(--text-light)' }}>Hold Candidate</span>
            <span style={{ fontSize: '1.4em', fontWeight: 'bold', color: 'var(--accent)' }}>
              {parseFloat(hold_price).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
            </span>
          </div>
        )}
      </div>

      {/* Badges / Metrics */}
      <div style={{ display: 'flex', gap: '10px', marginTop: '10px', flexWrap: 'wrap' }}>
        <div className="neu-panel-inner" style={{ flex: 1, textAlign: 'center', fontSize: '0.9em' }}>
          <span style={{ color: 'var(--text-light)', display: 'block', marginBottom: '4px' }}>Tests</span>
          <strong style={{ color: test_count >= 3 ? '#e74c3c' : 'inherit' }}>{test_count} {test_count >= 3 ? '(Max)' : ''}</strong>
        </div>
        <div className="neu-panel-inner" style={{ flex: 1, textAlign: 'center', fontSize: '0.9em' }}>
          <span style={{ color: 'var(--text-light)', display: 'block', marginBottom: '4px' }}>Candidate?</span>
          <strong style={{ color: hold_valid ? 'var(--accent)' : 'inherit' }}>{hold_valid ? 'YES' : 'NO'}</strong>
        </div>
        <div className="neu-panel-inner" style={{ flex: 1, textAlign: 'center', fontSize: '0.9em', backgroundColor: has_limit ? 'rgba(46, 204, 113, 0.1)' : (level.hold_tests > 0 ? 'rgba(52, 152, 219, 0.1)' : 'transparent') }}>
          <span style={{ color: 'var(--text-light)', display: 'block', marginBottom: '4px' }}>Limit Placed</span>
          <strong style={{ color: has_limit ? '#2ecc71' : (level.hold_tests > 0 ? '#3498db' : 'inherit') }}>
            {has_limit ? 'YES' : (level.hold_tests > 0 ? 'GETEST' : 'NO')}
          </strong>
        </div>
      </div>
      
      {/* Footer */}
      <div style={{ fontSize: '0.8em', color: 'var(--text-light)', textAlign: 'right', marginTop: '5px' }}>
        {new Date(timestamp).toLocaleTimeString()}
      </div>

    </div>
  );
}
