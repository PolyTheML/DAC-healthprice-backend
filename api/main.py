"""FastAPI application for DAC-UW Underwriting API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import cases, pricing, portfolio, dashboard, calibration

app = FastAPI(
    title="DAC-UW Underwriting API",
    description="Agentic medical underwriting platform for life insurance",
    version="0.1.0",
)

# CORS middleware: allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cases.router, prefix="/cases", tags=["cases"])
app.include_router(pricing.router, prefix="/pricing", tags=["pricing"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(calibration.router, prefix="/api/v1/calibration", tags=["calibration"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
