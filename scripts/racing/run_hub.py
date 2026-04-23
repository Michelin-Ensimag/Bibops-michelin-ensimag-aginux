"""Run the racing hub server."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "src.racing.hub.server:app",
        host="localhost",
        port=8000,
        reload=False,
        log_level="info",
    )
