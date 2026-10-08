# Notebooks

`project_analysis.ipynb` presents the research question, model rules,
experimental checks, figures, quantitative comparisons and limitations.
Install `requirements.txt` from the repository root, then open the notebook in
JupyterLab or VS Code and run all cells using the project environment's Python
kernel. It expects the full output files in `results/`; regenerate them with
`python -m experiments.run_all` if needed. One representative shocked/control
pair is simulated in the notebook, while the main analysis reads committed
multi-seed results.
