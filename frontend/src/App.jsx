// src/App.jsx
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import DockingViewer from './DockingViewer'; 
import './App.css';

export default function App() {
  const [view, setView] = useState('landing'); 
  const [pdbId, setPdbId] = useState('');
  const [prediction, setPrediction] = useState(null);
  const [isDocking, setIsDocking] = useState(false);
  const [dockingUrl, setDockingUrl] = useState(null);
  const [showShap, setShowShap] = useState(false);

  const handlePredict = async (e) => {
    e.preventDefault();
    if (!pdbId) return;
    
    setDockingUrl(null);
    setIsDocking(false);
    setShowShap(false);
    setPrediction(null);
    
    setView('loading');
    try {
      const res = await fetch('/predict_heme_binding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pdb_id: pdbId })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Prediction failed');
      
      setPrediction(data);
      setView('dashboard');
    } catch (err) {
      alert(err.message);
      setView('landing');
    }
  };

  const handleDocking = async () => {
    setIsDocking(true);
    setShowShap(true); 
    
    try {
      const res = await fetch('/run_docking', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: prediction.job_id,
          pdb_id: prediction.protein_id,
          pocket_data: prediction.best_pocket
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Docking failed');
      
      setDockingUrl(data.docking_result_url);
    } catch (err) {
      alert(err.message);
    } finally {
      setIsDocking(false);
    }
  };

  const handleReset = () => {
    setView('landing');
    setPdbId('');
    setPrediction(null);
    setDockingUrl(null);
    setShowShap(false);
  };

  const renderStructuredExplanation = (text) => {
    if (!text) return null;
    const lines = text.split('\n').filter(line => line.trim() !== '');
    const header = lines[0]; 
    const features = lines.slice(1); 

    return (
      <div className="explanation-card">
        <div className="explanation-header">
          Model Classification
        </div>
        <div className="explanation-body">
          <p style={{ marginBottom: '1rem', color: 'var(--text-main)', fontWeight: '500' }}>{header}</p>
          <ul className="feature-list">
            {features.map((feature, idx) => {
              const match = feature.match(/- The measurement for '(.+)' (strongly supported|reduced) binding probability\./);
              if (match) {
                const isPositive = match[2] === 'strongly supported';
                return (
                  <li key={idx} className="feature-item">
                    <span className="feature-icon" style={{ color: isPositive ? 'var(--success-text)' : 'var(--danger-text)' }}>
                      {isPositive ? '↑' : '↓'}
                    </span>
                    <span className="feature-text">
                      <strong>{match[1]}</strong> {match[2]} binding probability.
                    </span>
                  </li>
                );
              }
              return <li key={idx} className="feature-item">{feature}</li>;
            })}
          </ul>
        </div>
      </div>
    );
  };

  // Helper to render the 10 data points requested from the JSON
  const renderPocketStats = (pocket) => {
    const stats = [
      { label: "Volume", value: pocket.volume },
      { label: "Druggability", value: pocket.druggability_score },
      { label: "Total SASA", value: pocket.total_sasa },
      { label: "Apolar SASA", value: pocket.apolar_sasa },
      { label: "Polar SASA", value: pocket.polar_sasa },
      { label: "Flatness Index", value: pocket.pocket_flatness_index },
      { label: "Hydrophobicity", value: pocket.hydrophobicity_score },
      { label: "Alpha Spheres", value: pocket.number_of_alpha_spheres },
      { label: "Alpha Density", value: pocket.alpha_sphere_density },
      { label: "Charge Score", value: pocket.charge_score }
    ];

    return (
      <div className="stats-grid">
        {stats.map((stat, i) => (
          <div key={i} className="stat-box">
            <span className="stat-label">{stat.label}</span>
            <span className="stat-value">{stat.value !== undefined ? stat.value : 'N/A'}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="app-container">
      <AnimatePresence mode="wait">
        
        {/* --- LANDING PAGE --- */}
        {view === 'landing' && (
          <motion.div 
            key="landing"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="landing-container"
          >
            <h1 className="title">
              Heme<span>Discover</span>
            </h1>
            <p className="subtitle">
              A high-throughput machine learning pipeline for discovering novel Heme-binding proteins. 
              Enter a Protein Data Bank (PDB) ID to predict binding affinity and run in-silico docking.
            </p>
            
            <form onSubmit={handlePredict} className="search-form">
              <input 
                type="text" 
                placeholder="e.g., 1F74" 
                value={pdbId}
                onChange={(e) => setPdbId(e.target.value.toUpperCase())}
                className="search-input"
                maxLength={4}
              />
              <button type="submit" className="btn-primary">
                Analyze Structure
              </button>
            </form>
          </motion.div>
        )}

        {/* --- LOADING SCREEN --- */}
        {view === 'loading' && (
          <motion.div 
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="landing-container"
          >
            <h2 style={{ color: 'var(--text-muted)' }}>Extracting Features & Running LightGBM...</h2>
          </motion.div>
        )}

        {/* --- 1/3 & 2/3 DASHBOARD --- */}
        {view === 'dashboard' && prediction && (
          <motion.div 
            key="dashboard"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="dashboard-container"
          >
            {/* 1/3 INFO PANEL */}
            <div className="info-panel">
              <button onClick={handleReset} className="btn-text" style={{ marginBottom: '2rem' }}>
                &larr; New Search
              </button>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <h2>{prediction.protein_id}</h2>
              </div>
              
              {prediction.status === "Non-Binder" ? (
                <div style={{ backgroundColor: 'var(--danger-bg)', color: 'var(--danger-text)', padding: '1rem', borderRadius: '8px', border: '1px solid #fca5a5' }}>
                  <strong>{prediction.message}</strong>
                </div>
              ) : (
                <>
                  <div style={{ marginBottom: '2.5rem' }}>
                    <span style={{ fontSize: '2.5rem', color: 'var(--success-text)', fontWeight: '800', letterSpacing: '-1px' }}>
                      {prediction.confidence}
                    </span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem', fontWeight: '500', textTransform: 'uppercase', fontSize: '0.8rem', letterSpacing: '1px' }}>
                      Confidence Score
                    </span>
                  </div>

                  {renderStructuredExplanation(prediction.explanation)}
                  
                  {/* POCKET PARAMETERS GRID */}
                  <h4 style={{ textTransform: 'uppercase', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem', fontWeight: '700', letterSpacing: '1px' }}>
                    Pocket Topology ({prediction.best_pocket.Pocket_ID})
                  </h4>
                  {renderPocketStats(prediction.best_pocket)}
                  
                  <div style={{ marginBottom: '2rem' }}>
                    <h4 style={{ textTransform: 'uppercase', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem', fontWeight: '700', letterSpacing: '1px' }}>
                      Active Site Residues
                    </h4>
                    <div>
                      {prediction.residues_involved.map(res => (
                        <span key={res} className="residue-tag">{res}</span>
                      ))}
                    </div>
                  </div>

                  {/* DOWNLOAD ORIGINAL PDB BUTTON */}
                  <a 
                    href={`/workspace/${prediction.job_id}/pdb/${prediction.protein_id}.pdb`} 
                    download={`${prediction.protein_id}.pdb`}
                    className="btn-primary"
                    style={{ width: '100%', marginBottom: '2rem', backgroundColor: 'var(--bg-white)', color: 'var(--text-main)', border: '1px solid var(--border-color)' }}
                  >
                    ↓ Download Original .PDB File
                  </a>

                  {(isDocking || dockingUrl) && (
                    <>
                      <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '2rem 0' }} />
                      
                      <button onClick={() => setShowShap(!showShap)} className="btn-text" style={{ width: '100%', textAlign: 'center', padding: '1rem', border: '1px solid var(--accent-color)', borderRadius: '8px' }}>
                        {showShap ? "Hide SHAP Analysis" : "View Prediction Reason (SHAP)"}
                      </button>
                      
                      {showShap && (
                        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="shap-container">
                          <img 
                            src={prediction.shap_chart_url} 
                            alt="SHAP Analysis" 
                            className="shap-image"
                          />
                          {/* SHAP DOWNLOAD LINK */}
                          <a 
                            href={prediction.shap_chart_url} 
                            download={`${prediction.protein_id}_SHAP.png`}
                            style={{ display: 'block', textAlign: 'center', marginTop: '1rem', color: 'var(--accent-color)', fontSize: '0.9rem', fontWeight: '600' }}
                          >
                            ↓ Download SHAP Analysis (.PNG)
                          </a>
                        </motion.div>
                      )}
                    </>
                  )}
                </>
              )}
            </div>

            {/* 2/3 DOCKING ARENA */}
            <div className="docking-arena">
              {prediction.status === "Non-Binder" ? (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '1.25rem' }}>
                  No active site detected. Simulation aborted.
                </div>
              ) : !dockingUrl ? (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  {isDocking ? (
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ width: '3rem', height: '3rem', border: '4px solid var(--border-color)', borderTopColor: 'var(--accent-color)', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 1.5rem auto' }}></div>
                      <h3 style={{ color: 'var(--text-main)', fontSize: '1.5rem', marginBottom: '0.5rem' }}>
                        Running Monte Carlo Simulation...
                      </h3>
                      <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>(ETD: {prediction.docking_etd_seconds} seconds)</span>
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center' }}>
                      <button onClick={handleDocking} className="btn-dock">
                        Run 3D Docking Simulation
                      </button>
                      <p style={{ marginTop: '1.5rem', color: 'var(--text-muted)', fontSize: '1rem' }}>
                        Targeting <strong>{prediction.best_pocket.Pocket_ID}</strong>
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
                  
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div style={{ padding: '0.75rem 1.5rem', backgroundColor: 'var(--danger-bg)', color: 'var(--danger-text)', borderRadius: '8px', border: '1px solid #fca5a5' }}>
                      <span style={{ fontWeight: '700', marginRight: '0.5rem' }}>Auto-Delete Timer:</span> 
                      Server files will be wiped in 2 minutes.
                    </div>
                    {/* DOCKING RESULT PDBQT DOWNLOAD */}
                    <a href={dockingUrl} download className="btn-primary" style={{ padding: '0.75rem 1.5rem', backgroundColor: '#0f172a' }}>
                      ↓ Download Result (.PDBQT)
                    </a>
                  </div>
                  
                  <div className="viewer-wrapper">
                     <DockingViewer pdbId={prediction.protein_id} dockingUrl={dockingUrl} />
                  </div>
                </div>
              )}
            </div>

          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}