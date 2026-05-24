"""FastAPI app — serves static React build + JSON API + SSE streamed chat."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import Config, load_config
from ..engine.composio_tools import ComposioIntegration
from ..engine.experiment import ExperimentRunner
from ..engine.memory import VectorMemory
from ..engine.scheduler import Scheduler
from ..engine.store import Store
from .routes import brand as brand_route
from .routes import chat as chat_route
from .routes import experiments as experiments_route
from .routes import gallery as gallery_route
from .routes import memory as memory_route
from .routes import metrics as metrics_route
from .routes import templates as templates_route
from .routes import trust as trust_route

logger = logging.getLogger(__name__)


class AppState:
    """Singletons reachable from request handlers via app.state."""

    config: Config
    store: Store
    memory: VectorMemory
    composio: ComposioIntegration
    runner: ExperimentRunner
    scheduler: Scheduler | None


def create_app(config: Config | None = None) -> FastAPI:
    cfg = config or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(cfg.db_path)
        composio = ComposioIntegration(cfg.composio_api_key)
        memory = VectorMemory(store, cfg.llm)
        runner = ExperimentRunner(config=cfg, store=store, memory=memory, composio=composio)
        scheduler: Scheduler | None = None
        if cfg.scheduler.enabled:
            scheduler = Scheduler(config=cfg, store=store, runner=runner)
            scheduler.start()

        app.state.gtm = AppState()
        app.state.gtm.config = cfg
        app.state.gtm.store = store
        app.state.gtm.memory = memory
        app.state.gtm.composio = composio
        app.state.gtm.runner = runner
        app.state.gtm.scheduler = scheduler

        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.stop()
            store.close()

    app = FastAPI(
        title="GTM-OS",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict:
        gtm: AppState = app.state.gtm
        return {
            "ok": True,
            "version": __version__,
            "model": gtm.config.llm.model,
            "scheduler_running": bool(gtm.scheduler and gtm.scheduler.running),
            "composio_configured": gtm.composio.configured,
            "primitives_dir": str(gtm.config.primitives_dir),
        }

    app.include_router(brand_route.router, prefix="/api")
    app.include_router(chat_route.router, prefix="/api")
    app.include_router(experiments_route.router, prefix="/api")
    app.include_router(gallery_route.router, prefix="/api")
    app.include_router(memory_route.router, prefix="/api")
    app.include_router(metrics_route.router, prefix="/api")
    app.include_router(templates_route.router, prefix="/api")
    app.include_router(trust_route.router, prefix="/api")

    # Initialize the gallery from the gallery/ directory.
    gallery_dir = cfg.project_root / "gallery"
    if gallery_dir.exists():
        gallery_route.init_gallery(str(gallery_dir))

    # Static frontend.
    frontend_dir = Path(__file__).resolve().parent / "frontend_dist"
    if (frontend_dir / "index.html").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(frontend_dir / "assets")),
            name="assets",
        )

        @app.get("/")
        async def index_root() -> FileResponse:
            return FileResponse(frontend_dir / "index.html")

        @app.get("/{full_path:path}")
        async def index_catchall(full_path: str):
            asset_path = frontend_dir / full_path
            if asset_path.is_file():
                return FileResponse(asset_path)
            return FileResponse(frontend_dir / "index.html")
    else:

        @app.get("/")
        async def no_frontend() -> JSONResponse:
            return JSONResponse(
                {
                    "ok": True,
                    "message": (
                        "GTM-OS API is running, but the frontend hasn't been built yet. "
                        "Run `cd frontend && npm install && npm run build` to build the UI."
                    ),
                    "docs": "/docs",
                }
            )

    return app


def main() -> None:  # pragma: no cover — uvicorn entry
    import uvicorn

    cfg = load_config()
    uvicorn.run(
        "gtm_os.server.app:create_app",
        factory=True,
        host=cfg.server.host,
        port=cfg.server.port,
        reload=False,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
