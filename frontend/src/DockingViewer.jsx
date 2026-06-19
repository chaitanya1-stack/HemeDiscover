import React, { useEffect, useRef, useState } from 'react';

export default function DockingViewer({ pdbId, dockingUrl }) {
  const viewerRef = useRef(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!dockingUrl) return;

    // 1. Check if 3Dmol is loaded. If not, dynamically inject it and wait.
    if (!window.$3Dmol) {
      console.log("Downloading 3Dmol.js library...");
      const script = document.createElement('script');
      script.src = "https://3Dmol.org/build/3Dmol-min.js";
      script.async = true;
      script.onload = () => setIsReady(true); // Triggers the re-render once loaded
      document.body.appendChild(script);
      return;
    }

    // 2. The main rendering function
    const render3D = async () => {
      try {
        console.log("Starting 3D render...");
        
        // Clear any old instances to prevent ghosting
        viewerRef.current.innerHTML = '';
        
        const viewer = window.$3Dmol.createViewer(viewerRef.current, { 
          backgroundColor: '#f8fafc' 
        });

        // --- Fetch and Render Protein ---
        console.log(`Fetching protein: ${pdbId}`);
        const proteinRes = await fetch(`https://files.rcsb.org/download/${pdbId}.pdb`);
        if (!proteinRes.ok) throw new Error("Could not download Protein from RCSB.");
        const proteinData = await proteinRes.text();
        
        viewer.addModel(proteinData, 'pdb');
        viewer.setStyle({model: 0}, {cartoon: {color: 'spectrum'}});
        
        // Use VDW instead of SAS. It is 10x faster and won't crash your browser.
        viewer.addSurface(window.$3Dmol.SurfaceType.VDW, {opacity: 0.5, color: 'white'}, {model: 0});

        // --- Fetch and Render Ligand ---
        console.log(`Fetching docked ligand: ${dockingUrl}`);
        const ligandRes = await fetch(dockingUrl);
        if (!ligandRes.ok) throw new Error("Could not fetch the docked PDBQT file from your server.");
        const ligandData = await ligandRes.text();
        
        viewer.addModelsAsFrames(ligandData, 'pdbqt');
        viewer.setStyle({model: 1}, {stick: {colorscheme: 'cyanCarbon', radius: 0.2}});

        viewer.zoomTo();
        viewer.render();
        console.log("Render complete!");
        
      } catch (error) {
        console.error("3D Viewer Error:", error);
        // Show the error directly on the screen so you don't have to hunt for it
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
  }, [pdbId, dockingUrl, isReady]); // isReady ensures it runs AGAIN after the script downloads

  return (
    <div 
      ref={viewerRef} 
      style={{ width: '100%', height: '100%', minHeight: '500px', position: 'relative' }} 
    />
  );
}