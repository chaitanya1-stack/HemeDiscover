# HemeDiscover 🔬

**An AI-Powered Bioinformatics Pipeline for Heme-Binding Site Discovery**

HemeDiscover is a robust, full-stack pipeline engineered to solve a core problem in structural biology: **The High-Throughput Identification of Heme-Binding Pockets.**

Traditional structural bioinformatics tools are often "shape-blind" to chemical specificity, leading to high false-positive rates when encountering hydrophobic "decoy" pockets. HemeDiscover solves this using a hybrid architecture that integrates **geometric tessellation, chemical feature engineering, and machine learning inference.**

---

## 🧪 Scientific Methodology

The pipeline follows a rigorous four-phase workflow, optimized for chemical accuracy and structural specificity.

### Phase I: Geometric Tessellation (The "Geometer")
We treat the protein as a volumetric field using Voronoi tessellation (via `fpocket`). This identifies "Alpha Spheres"—clusters of empty space representing internal protein voids.
- **Key Extracted Features:**
    - **Total SASA & Apolar SASA:** Essential for filtering out hydrophilic surface cracks and identifying the hydrophobic, sequestered cores required for Heme binding.
    - **Volume & Alpha Sphere Density:** High-density spheres within a high-volume cavity are statistically indicative of deep, druggable pockets.
    - **Flatness Index:** A filter to distinguish between "tunnel-like" cavities and the spherical/globular cavities preferred by the Heme-porphyrin ring.

### Phase II: Chemical Feature Engineering (The "Chemist")
A pocket is only functional if it provides the correct chemical micro-environment. We extract specific features based on conserved protein-ligand binding theory:
- **Coordination Motif Detection:** The model scans for specific residues (His, Cys, Tyr) that coordinate the Heme iron center.
- **Charge Score:** We analyze the electrostatic potential within the pocket to ensure it matches the Heme-iron coordination geometry.
- **Hydrophobicity Index:** Quantifies the "oily" nature of the pocket walls, ensuring compatibility with the hydrophobic porphyrin ring.

### Phase III: Machine Learning Inference (The "Decider")
We utilize a **LightGBM (Gradient Boosting)** model trained on verified Heme-binding sites. 
- **Explainability:** We integrate **SHAP (SHapley Additive exPlanations)** to ensure transparency. This allows users to see *why* a site was flagged—was it the pocket volume, the hydrophobicity, or the specific Histidine residues?
- **Filtering Logic:** The model acts as a "chemical sensor" that overrides the purely geometric findings of `fpocket`, effectively rejecting decoy cavities that are geometrically perfect but chemically inert.

### Phase IV: Physical Validation (The "Physicist")
Only sites passing the ML confidence threshold (>35%) proceed to **AutoDock Vina** simulations.
- **Monte Carlo Iterative Search:** The pipeline iterates through thousands of ligand orientations to find the global minimum energy state.
- **Energy Minimization:** The binding affinity (kcal/mol) is calculated, providing the final physical proof of concept.

---

## 🛠 Tech Stack

* **Backend:** Python (FastAPI, Uvicorn)
* **ML/Data:** LightGBM, Scikit-Learn, Pandas, NumPy
* **Bioinformatics:** `fpocket` (Geometry), AutoDock Vina (Docking)
* **Frontend:** React.js, Framer Motion, 3Dmol.js (3D Visualization)
* **Deployment:** Docker, Hugging Face Spaces

---
