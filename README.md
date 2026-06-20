# HemeDiscover 🔬

## Overview
HemeDiscover is an AI-powered bioinformatics pipeline for the automated discovery and validation of Heme-binding sites in protein structures. It moves beyond standard geometric pocket detection by integrating machine learning and molecular docking to ensure biological relevance.

---

## 🧬 Scientific Methodology

HemeDiscover operates as a multi-stage decision engine, mimicking the logical steps of a structural biologist:

### Phase I: Geometric Extraction (The Geometer)
We utilize **Voronoi tessellation** via `fpocket` to represent protein cavities as clusters of Alpha Spheres. 
- **Key Metrics:** We calculate the Total Solvent Accessible Surface Area (SASA) and Apolar SASA. 
- **Logic:** Heme is a hydrophobic ligand. By filtering for cavities with high Apolar SASA, we discard small, hydrophilic surface cracks, focusing only on large, hydrophobic, sequestered protein cavities.

### Phase II: Chemical Feature Engineering & ML Inference (The Chemist)
A geometric pocket is not inherently functional. Our custom LightGBM model validates the **chemical micro-environment**.
- **The Coordination Motif:** The model analyzes the amino acid composition within the pocket, specifically looking for Histidine (His), Cysteine (Cys), or Tyrosine (Tyr) residues, which are essential for coordinating the Heme iron atom.
- **Explainability (SHAP):** We use SHAP (SHapley Additive exPlanations) to provide model transparency. When the pipeline flags a protein, it provides a breakdown of which features (e.g., volume, charge score, specific residues) contributed to the confidence score, ensuring the prediction is scientifically verifiable.

### Phase III: Physical Validation (The Physicist)
Once the ML model confirms a site is theoretically capable of binding, we perform physical validation using **AutoDock Vina**.
- **Simulation:** We conduct a Monte Carlo iterated local search to find the lowest energy binding state of the Heme ligand within the identified pocket.
- **Affinity Scoring:** Vina calculates the binding affinity (kcal/mol), accounting for steric clashes, hydrophobic contacts, and electrostatic stability. 

### Phase IV: Fault-Tolerant Engineering (The Architect)
To ensure production stability, the pipeline includes "Fail-Fast" logic:
- **Apo-State Protection:** The pipeline detects wide-open protein conformations (where no enclosed cavity exists) to prevent pipeline crashes.
- **Decoy Rejection:** By training on specific heme-binding enzymes (e.g., Myoglobin) and testing against generalist carriers (e.g., Human Serum Albumin), the model differentiates between "sticky" protein surfaces and specific functional active sites.

---

## 🛠 Tech Stack

* **Backend:** Python, FastAPI, Uvicorn
* **ML Engine:** LightGBM, Scikit-Learn
* **Docking Engine:** AutoDock Vina
* **Frontend:** React.js, Framer Motion, 3Dmol.js
* **Deployment:** Docker, Hugging Face Spaces

---

## 🚀 Usage

1. **Input:** Submit a PDB ID or upload a custom `.pdb` structure.
2. **Analysis:** The pipeline extracts pockets and runs the LightGBM inference model.
3. **Validation:** Analyze the SHAP report to confirm chemical suitability.
4. **Docking:** Initiate the Vina docking simulation to confirm physical affinity.
5. **Output:** Download the cleaned, docked PDB files for further analysis.

---

## 🎓 About the Developer
Developed by **Chaitanya**, as a capstone project in bioinformatics and machine learning engineering. This pipeline demonstrates the integration of heavy computational biology tools with modern web architecture.
