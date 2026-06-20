FROM python:3.10-slim

# 1. Install standard scientific binaries and system library dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    fpocket \
    autodock-vina \
    openbabel \
    libxrender1 \
    libxext6 \
    libx11-6 \
    libexpat1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Symlink system binaries if they use non-standard names
# (Ensures your python code can cleanly call ['vina', ...] and ['obabel', ...])
RUN ln -s /usr/bin/autodock-vina /usr/bin/vina || true

# 3. Security & Compliance: Establish Hugging Face generic user environment
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# 4. Define active execution workspace
WORKDIR /app

# 5. Copy configuration targets first to cache pip layers efficiently
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 6. Copy core modules and binary artifacts into the container 
# (Make sure your model weights and ligand template are in your root folder)
COPY --chown=user . /app

# 7. Create an isolated transient directory layout with permissions enabled
RUN mkdir -p /app/temp_data && chmod 777 /app/temp_data

# 8. Expose standard Hugging Face interface layer
EXPOSE 7860

# 9. Launch the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]