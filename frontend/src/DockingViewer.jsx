import React, { useEffect, useRef, useState } from 'react';

export default function DockingViewer({ pdbId, dockingUrl }) {
  const viewerRef = useRef(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!dockingUrl || !pdbId) return;

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
        viewerRef.current.innerHTML = '';
        
        const viewer = window.$3Dmol.createViewer(viewerRef.current, { 
          backgroundColor: '#f8fafc' 
        });

        // --- FETCH RAW DATA FROM RCSB ---
        console.log(`Fetching protein from RCSB: ${pdbId}`);
        const proteinRes = await fetch(`https://files.rcsb.org/download/${pdbId}.pdb`);
        if (!proteinRes.ok) throw new Error("Could not download Protein from RCSB.");
        const rawPdbText = await proteinRes.text();

        // --- FRONTEND APO-FICATION (Strict Training Parity) ---
        const cleanedPdbText = rawPdbText.split('\n').filter(line => {
            if (line.startsWith("HETATM") && line.includes("HEM")) {
                return false; // Only drop HEM
            }
            return true; // Keep everything else
        }).join('\n');

        // Pass the CLEANED text string to 3Dmol
        viewer.addModel(cleanedPdbText, 'pdb');
        viewer.setStyle({model: 0}, {cartoon: {color: 'spectrum'}});
        viewer.addSurface(window.$3Dmol.SurfaceType.VDW, {opacity: 0.5, color: 'white'}, {model: 0});

        // --- Fetch and Render Ligand ---
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
            <div style="display:flex; height:100%; align-items:center; justify-content:center; color:#991b1b; padding:2rem; text-align:center;">
              <b>Failed to load 3D models:</b><br/>${error.message}
            </div>
          `;
        }
      }
    };

    render3D();
  }, [pdbId, dockingUrl, isReady]);

  return (
    <div 
      ref={viewerRef} 
      style={{ width: '100%', height: '100%', minHeight: '500px', position: 'relative' }} 
    />
  );
}