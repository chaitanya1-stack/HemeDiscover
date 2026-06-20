import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import DockingViewer from './DockingViewer'; 
import './App.css';
const API_BASE_URL = 'https://ck758779-hemediscover.hf.space';


export default function App() {
  const [view, setView] = useState('landing'); 
  const [pdbId, setPdbId] = useState('');
  const [pdbFile, setPdbFile] = useState(null); 
  
  const [prediction, setPrediction] = useState(null);
  const [isDocking, setIsDocking] = useState(false);
  const [dockingStatus, setDockingStatus] = useState(''); 
  const [dockingUrl, setDockingUrl] = useState(null);
  const [affinityScore, setAffinityScore] = useState(null);
  const [showShap, setShowShap] = useState(false);

  const handlePredict = async (e) => {
    e.preventDefault();
    if (!pdbId && !pdbFile) return;
    
    setDockingUrl(null);
    setAffinityScore(null);
    setIsDocking(false);
    setDockingStatus('');
    setShowShap(false);
    setPrediction(null);
    
    setView('loading');
    
    const formData = new FormData();
    if (pdbFile) {
      formData.append('file', pdbFile);
    } else if (pdbId) {
      formData.append('pdb_id', pdbId);
    }

    try {
      const res = await fetch(`${API_BASE_URL}/predict_heme_binding`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Prediction failed');
      
      setPrediction(data);
      // Immediately show SHAP insights as soon as prediction completes
      setShowShap(true); 
      setView('dashboard');
    } catch (err) {
      alert(err.message);
      setView('landing');
    }
  };

  const handleDocking = async () => {
    setIsDocking(true);
    setDockingStatus('Initializing Monte Carlo simulations...');
    
    try {
      const res = await fetch(`${API_BASE_URL}/run_docking`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: prediction.job_id,
          pdb_id: prediction.protein_id,
          pockets_data: prediction.top_pockets 
        })
      });

      if (!res.body) throw new Error('Streaming not supported by browser.');

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n').filter(line => line.trim() !== '');

        for (const line of lines) {
          const parsed = JSON.parse(line);
          
          if (parsed.status === 'Started' || parsed.status === 'Progress' || parsed.status === 'Calculating') {
            setDockingStatus(parsed.message); 
          } else if (parsed.status === 'Error') {
            console.error("Docking Error:", parsed.message);
          } else if (parsed.status === 'Complete') {
            setDockingUrl(parsed.best_docking_result_url);
            setAffinityScore(parsed.best_affinity_score);
          }
        }
      }
    } catch (err) {
      alert(err.message);
    } finally {
      setIsDocking(false);
      setDockingStatus('');
    }
  };

  const handleReset = () => {
    setView('landing');
    setPdbId('');
    setPdbFile(null);
    setPrediction(null);
    setDockingUrl(null);
    setAffinityScore(null);
    setShowShap(false);
  };

  const renderStructuredExplanation = (text) => {
    if (!text) return null;
    const lines = text.split('\n').filter(line => line.trim() !== '');
    const header = lines[0]; 
    const features = lines.slice(1); 

    return (
      <div className="explanation-card" style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#f8fafc', borderRadius: '8px', textAlign: 'left', border: '1px solid var(--border-color)' }}>
        <p style={{ fontWeight: 'bold', marginBottom: '0.75rem', color: 'var(--text-main)' }}>{header}</p>
        <ul style={{ listStyleType: 'none', padding: 0, margin: 0 }}>
          {features.map((feature, idx) => {
            const match = feature.match(/- The measurement for '(.+)' (strongly supported|reduced) binding probability\./);
            if (match) {
              const isPositive = match[2] === 'strongly supported';
              return (
                <li key={idx} style={{ marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                  <span style={{ color: isPositive ? '#16a34a' : '#dc2626', marginRight: '0.5rem', fontWeight: '900' }}>
                    {isPositive ? '↑' : '↓'}
                  </span>
                  <strong>{match[1]}</strong> {match[2]} binding.
                </li>
              );
            }
            return <li key={idx} style={{ fontSize: '0.9rem' }}>{feature}</li>;
          })}
        </ul>
      </div>
    );
  };

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
          <div key={i} className="stat-box" style={{ padding: '0.5rem', backgroundColor: 'var(--bg-white)', borderRadius: '4px', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column' }}>
            <span className="stat-label" style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 'bold' }}>{stat.label}</span>
            <span className="stat-value" style={{ fontSize: '0.9rem', color: 'var(--text-main)', fontWeight: '500' }}>{stat.value !== undefined ? stat.value : 'N/A'}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="app-container">
      <AnimatePresence mode="wait">
        
        {view === 'landing' && (
          <motion.div key="landing" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="landing-container">
            <h1 className="title">Heme<span>Discover</span></h1>
            <p className="subtitle">
              A high-throughput machine learning pipeline for discovering novel Heme-binding proteins. 
              Enter a Protein Data Bank (PDB) ID or upload a de novo .pdb file.
            </p>
            
            <form onSubmit={handlePredict} className="search-form" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%', maxWidth: '400px', margin: '0 auto' }}>
              
              <div style={{ position: 'relative' }}>
                <input 
                  type="text" 
                  placeholder="Enter PDB ID (e.g., 1F74)" 
                  value={pdbId} 
                  onChange={(e) => { setPdbId(e.target.value.toUpperCase()); setPdbFile(null); }} 
                  className="search-input" 
                  maxLength={4} 
                  disabled={!!pdbFile}
                  style={{ width: '100%', opacity: pdbFile ? 0.5 : 1 }}
                />
              </div>

              <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontWeight: 'bold' }}>OR</div>
              
              <div style={{ position: 'relative' }}>
                <input 
                  type="file" 
                  accept=".pdb"
                  onChange={(e) => { setPdbFile(e.target.files[0]); setPdbId(''); }} 
                  className="search-input" 
                  disabled={!!pdbId}
                  style={{ width: '100%', opacity: pdbId ? 0.5 : 1, padding: '0.75rem', fontSize: '0.9rem' }}
                />
              </div>

              <button type="submit" className="btn-primary" style={{ marginTop: '1rem' }}>
                Analyze Structure
              </button>
            </form>
          </motion.div>
        )}

        {view === 'loading' && (
          <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="landing-container">
            <div className="spinner"></div>
            <h2 style={{ color: 'var(--text-muted)' }}>Extracting Features & Running LightGBM...</h2>
          </motion.div>
        )}

        {view === 'dashboard' && prediction && (
          <motion.div key="dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="dashboard-container">
            
            <div className="info-panel">
              <button onClick={handleReset} className="btn-text" style={{ marginBottom: '2rem' }}>&larr; New Search</button>
              
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
                      {prediction.top_pocket_confidence}
                    </span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem', fontWeight: '500', textTransform: 'uppercase', fontSize: '0.8rem', letterSpacing: '1px' }}>
                      Max Confidence
                    </span>
                  </div>

                  <h4 style={{ textTransform: 'uppercase', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem', fontWeight: '700', letterSpacing: '1px' }}>
                    Identified Targets ({prediction.top_pockets.length} Pockets)
                  </h4>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.5rem' }}>
                    {prediction.top_pockets.map((pocket, idx) => (
                      <div key={idx} style={{ padding: '1rem', border: '1px solid var(--border-color)', borderRadius: '8px', backgroundColor: idx === 0 ? '#f0fdf4' : 'transparent', borderColor: idx === 0 ? '#86efac' : 'var(--border-color)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                          <strong style={{ color: 'var(--text-main)' }}>{pocket.Pocket_ID}</strong>
                          {idx === 0 && <span style={{ fontSize: '0.7rem', backgroundColor: '#22c55e', color: 'white', padding: '2px 6px', borderRadius: '4px', fontWeight: 'bold' }}>BEST</span>}
                        </div>
                        <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          <span>Vol: {pocket.volume?.toFixed(1) || 'N/A'}</span>
                          <span>Spheres: {pocket.number_of_alpha_spheres || 'N/A'}</span>
                          <span>Score: {pocket.score?.toFixed(2) || 'N/A'}</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div style={{ marginBottom: '2rem' }}>
                    <h4 style={{ textTransform: 'uppercase', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem', fontWeight: '700', letterSpacing: '1px' }}>
                      Top Pocket Detailed Topology
                    </h4>
                    {renderPocketStats(prediction.top_pockets[0])}
                  </div>

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

                  {/* Cleaned PDB Download Button */}
                  <a 
                    href={`${API_BASE_URL}/workspace/${prediction.job_id}/raw/${prediction.protein_id}.pdb`} 
                    download={`${prediction.protein_id}_cleaned.pdb`} 
                    className="btn-primary" 
                    style={{ display: 'block', textAlign: 'center', textDecoration: 'none', width: '100%', marginBottom: '2rem', backgroundColor: 'var(--bg-white)', color: 'var(--text-main)', border: '1px solid var(--border-color)' }}
                  >
                    ↓ Download Cleaned .PDB File
                  </a>

                  {/* SHAP section separated from the docking loop entirely */}
                  <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '2rem 0' }} />
                  <button onClick={() => setShowShap(!showShap)} className="btn-text" style={{ width: '100%', textAlign: 'center', padding: '1rem', border: '1px solid var(--accent-color)', borderRadius: '8px', cursor: 'pointer' }}>
                    {showShap ? "Hide SHAP Analysis" : "View Prediction Reason (SHAP)"}
                  </button>
                  
                  <AnimatePresence>
                    {showShap && (
                      <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="shap-container" style={{ overflow: 'hidden' }}>
                        <img src={`${API_BASE_URL}${prediction.shap_chart_url}`} alt="SHAP Analysis" className="shap-image" style={{ width: '100%', height: 'auto', marginTop: '1rem' }} />
                        {renderStructuredExplanation(prediction.explanation)}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </>
              )}
            </div>

            <div className="docking-arena">
              {prediction.status === "Non-Binder" ? (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '1.25rem' }}>
                  No active site detected. Simulation aborted.
                </div>
              ) : !dockingUrl ? (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  {isDocking ? (
                    <div style={{ textAlign: 'center' }}>
                      <div className="spinner"></div>
                      <h3 style={{ color: 'var(--text-main)', fontSize: '1.5rem', marginBottom: '0.5rem', marginTop: '1rem', fontFamily: 'monospace' }}>
                        {dockingStatus}
                      </h3>
                      <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>(Max ETD: {prediction.docking_etd_seconds} seconds)</span>
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center' }}>
                      <button onClick={handleDocking} className="btn-dock">
                        Run Docking on Top {prediction.top_pockets.length} Pockets
                      </button>
                      <p style={{ marginTop: '1rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                        Pipeline will evaluate {prediction.top_pockets.length} sites and return the best affinity score.
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <div className="docking-header">
                    <div className="badge-group">
                      <div className="badge badge-success"><span>Best Affinity Score:</span><span>{affinityScore} kcal/mol</span></div>
                      <div className="badge badge-danger"><span>Auto-Delete Timer:</span>Files wipe in 2 mins.</div>
                    </div>
                    {/* Docking Result Download Button */}
                    <a 
                      href={`${API_BASE_URL}${dockingUrl}`} 
                      download 
                      className="btn-primary" 
                      style={{ display: 'block', textAlign: 'center', textDecoration: 'none', backgroundColor: '#0f172a' }}
                    >
                      ↓ Download Best Result
                    </a>
                  </div>
                  
                  <div className="viewer-wrapper">
                     <DockingViewer pdbId={prediction.protein_id} jobId={prediction.job_id} dockingUrl={`${API_BASE_URL}${dockingUrl}`} />
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