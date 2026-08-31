from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from database import engine, Base
from routers import webhook, orders

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="OrderStream AI")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router, prefix="/api/webhook", tags=["webhook"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])

# Mount static files for the dashboard
app.mount("/dashboard", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
def root():
    return RedirectResponse(url="/dashboard/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
