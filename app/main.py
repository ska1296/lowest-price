"""
FastAPI application for the Ultimate Price Comparison API.

This module sets up the FastAPI application with a clean functional architecture.
All business logic is handled by services, and routers only handle HTTP concerns.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services import price_comparison_service
from app.routers import search, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles service initialization on startup and cleanup on shutdown.
    """
    # Startup
    print("Initializing Price Comparison Service...")
    await price_comparison_service.initialize()
    print("Service initialized successfully.")
    yield

    # Shutdown
    print("Application shutting down.")


# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    lifespan=lifespan,
    description="A robust, backend-only tool that can reliably fetch the best price for a given product.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routers
app.include_router(search.router)
app.include_router(health.router)
