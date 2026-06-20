import React, { useEffect, useRef, useState } from 'react';
const API_BASE_URL = 'https://ck758779-hemediscover.hf.space';

export default function DockingViewer({ pdbId, jobId, dockingUrl }) {
  const viewerRef = useRef(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!dockingUrl || !pdbId || !jobId) return;

    if (!window.$3Dmol) {
      console.log("Downloading 3Dmol.js library...");
      const script = document.createElement('script');
      script.src = "https://3Dmol.org/build/3Dmol-min.js";
      script.async = true;
      script.onload = () => setIsReady(true);
      document.body.appendChild(script);
      return;
    }

    const render3D = async () => {
      try {
        console.log("Starting 3D render...");
        if (viewerRef.current) {
          viewerRef.current.innerHTML = '';
        }
        
        const viewer = window.$3Dmol.createViewer(viewerRef.current, { 
          backgroundColor: '#f8fafc' 
        });

        console.log(`Fetching structurally clean protein from server workspace...`);
        const proteinRes = await fetch(`${API_BASE_URL}/workspace/${jobId}/raw/${pdbId}.pdb`);
        if (!proteinRes.ok) throw new Error("Could not download the cleaned Protein from your backend workspace.");
        const cleanedPdbText = await proteinRes.text();

        viewer.addModel(cleanedPdbText, 'pdb');
        viewer.setStyle({model: 0}, {cartoon: {color: 'spectrum'}});
        viewer.addSurface(window.$3Dmol.SurfaceType.VDW, {opacity: 0.5, color: 'white'}, {model: 0});

        console.log(`Fetching docked ligand: ${dockingUrl}`);
        const ligandRes = await fetch(dockingUrl);
        if (!ligandRes.ok) throw new Error("Could not fetch the docked PDBQT file from your server.");
        const ligandData = await ligandRes.text();
        
        viewer.addModelsAsFrames(ligandData, 'pdbqt');
        viewer.setStyle({model: 1}, {stick: {colorscheme: 'greenCarbon', radius: 0.3}});

        viewer.zoomTo();
        viewer.render();
        console.log("Render complete!");
        
      } catch (error) {
        console.error("3D Viewer Error:", error);
        if (viewerRef.current) {
          viewerRef.current.innerHTML = `
            <div style="display:flex; height:100%; align-items:center; justify-content:center; flex-direction:column; color:#991b1b; padding:2rem; text-align:center;">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-bottom: 1rem;">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <b>Failed to load 3D models:</b>
              <span style="margin-top: 0.5rem; font-size: 0.9rem;">${error.message}</span>
            </div>
          `;
        }
      }
    };

    render3D();
  }, [pdbId, jobId, dockingUrl, isReady]);

  return (
    <div 
      ref={viewerRef} 
      style={{ 
        width: '100%', 
        height: '100%', 
        minHeight: '500px', 
        position: 'relative',
        borderRadius: '8px',
        overflow: 'hidden',
        border: '1px solid var(--border-color)'
      }} 
    />
  );
}