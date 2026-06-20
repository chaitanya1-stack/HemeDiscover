# HemeDiscover 🔬

**An AI-Powered Bioinformatics Pipeline for Heme-Binding Site Discovery**

HemeDiscover is a production-grade bioinformatics engine designed to address the "false-positive" crisis in structural biology. While traditional tools can easily identify hollow spaces within a protein, they fail to distinguish between generic hydrophobic cavities and functional Heme-binding sites. HemeDiscover bridges this gap by integrating geometric tessellation, high-dimensional biochemical feature engineering, and machine learning inference.

---

## 🧪 Scientific Methodology: The Four-Phase Workflow

The pipeline treats protein structural analysis as a multi-stage logic problem, moving from raw geometry to physical simulation.

### Phase I: Geometric Tessellation (The "Geometer")
We utilize Voronoi tessellation (via `fpocket`) to model the protein's interior as a volumetric field. This identifies "Alpha Spheres"—clusters of empty space representing internal protein voids.



* **Topological Analysis:** We compute the `Total SASA` and `Apolar SASA` to discard surface-level hydrophilic cracks, isolating only deep-seated, hydrophobic cavities suitable for Heme sequestration.
* **Dimensionality:** Metrics like `alpha_sphere_density`, `volume`, and `pocket_flatness_index` are extracted to characterize the size and shape of the pocket, filtering out tunnel-like configurations that cannot accommodate the Heme porphyrin ring.

### Phase II: Chemical Feature Engineering (The "Chemist")
A pocket is only functional if it possesses the correct chemical micro-environment. We extract 35+ high-dimensional features per pocket to create a biological "fingerprint." These features are categorized into four core domains:



1.  **Residue Composition (The Coordination Motif):** We quantify the count and density of key amino acids—`HIS`, `CYS`, `MET`, `TYR`, `PHE`, and `TRP`. These residues are essential for the coordination of the Heme iron center.
2.  **Advanced Motifs:** The pipeline detects conserved patterns such as the `CP` and `CXXCH` motifs, which are statistically linked to covalent Heme attachment and metal coordination.
3.  **Electrostatic/Thermodynamic Profile:** We analyze the `charge_score` and `polarity_score`. Specifically, we extract a `propionate_stabilization_score` (sum of `ARG` + `LYS`), as Heme propionate groups require cationic stabilization within the pocket.
4.  **Hydrophobic Environment:** We measure `mean_local_hydrophobic_density` and `apolar_alpha_sphere_proportion` to ensure the environment is "oily" enough to accommodate the hydrophobic porphyrin ring.

### Phase III: Machine Learning Inference (The "Decider")
We utilize a **LightGBM (Gradient Boosting)** classifier. Unlike linear models, LightGBM captures the non-linear, multi-variate relationships between these 35 features.

**Model Performance Metrics:**

| Model | PR AUC | F1 Score |
| :--- | :--- | :--- |
| Logistic Regression | 0.477 | 0.539 |
| SVM (RBF Kernel) | 0.727 | 0.667 |
| Random Forest | 0.771 | 0.607 |
| **Optimized LightGBM (Final)** | **0.795** | **0.710** |

* **Optimization Logic:** The model is optimized at a `0.35` probability threshold. This "aggressive recall" strategy ensures we capture subtle, non-canonical binding sites, while downstream physical validation (Phase IV) filters out any remaining false positives.
* **Explainability (XAI):** We leverage **SHAP** to map model predictions back to specific biological features, providing a transparency layer that confirms if a flag was triggered by critical residues (e.g., `HIS` count) rather than geometric artifacts.

### Phase IV: Physical Validation (The "Physicist")
Once the ML classifier flags a pocket, it proceeds to **AutoDock Vina** for physical simulation.



* **Monte Carlo Search:** The system executes an iterated local search to identify the global minimum energy binding conformation of the Heme ligand within the 3D grid.
* **Affinity Scoring:** This provides the final binding affinity (kcal/mol), confirming physical stability and verifying that the ML inference matches the laws of thermodynamics.

---

## 🛠 Tech Stack

* **Backend:** Python (FastAPI, Uvicorn)
* **ML/Data Engine:** LightGBM, Scikit-Learn, Pandas (feature matrix manipulation), NumPy
* **Bioinformatics:** `fpocket` (Tessellation), AutoDock Vina (Docking)
* **Frontend:** React.js, Framer Motion, 3Dmol.js (3D structural visualization)
* **Deployment:** Docker, Hugging Face Spaces

---

## 🎓 About the Developer
Developed by **Chaitanya**. This pipeline represents a production-grade application of bioinformatics principles, bridging the gap between raw PDB data and actionable molecular insights.
