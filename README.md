# Zomato Clone Application

This is a phase-based architecture for the Zomato AI Recommendation project.

## Production Deployment Step (e.g., Render Free Tier)

To ensure the backend starts within the restricted memory limits (like 512MB RAM on Render) and passes health checks quickly without downloading large datasets on the fly, follow these steps before deployment:

1. **Run Ingestion Locally**: 
   Before deploying, generate the cleaned dataset on your local machine.
   ```bash
   python -m phases.phase_1_data_ingestion.backend.data_ingestion.zomato_ingestion
   ```
   This will download the HuggingFace dataset, clean it, and save the result to `data/zomato_cleaned.parquet`.

2. **Deploy Cleaned Dataset**:
   Ensure the `data/zomato_cleaned.parquet` file is available to your production server. If the dataset is small enough (<100MB), you can commit it to Git using Git LFS or direct commit. For larger datasets, prepare external storage (e.g., AWS S3) and integrate a download step that doesn't bloat the application memory on startup. 
   
   *Note: In this setup, auto-download from HuggingFace on backend startup is disabled to explicitly prevent memory spikes on deployment.*

3. **Backend Startup**:
   The backend will now lazy-load the `zomato_cleaned.parquet` file upon the first request or at startup and cache it globally. If the dataset is missing, the backend will fail to start with a clear error requiring manual ingestion.
