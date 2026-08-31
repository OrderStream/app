from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import models
from database import engine, SessionLocal
from routers import webhook, orders
from services.seeder import seed_default_data

# Initialize Database Schema
models.Base.metadata.create_all(bind=engine)

# Auto-seed default bakery catalog & customer directory
try:
    db = SessionLocal()
    seed_default_data(db)
    db.close()
except Exception as e:
    print(f"Database Seeding Notice: {e}")

app = FastAPI(title="OrderStream AI - Wholesale Order Operating System")

# Mount Static Assets
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include Routers
app.include_router(webhook.router, prefix="/api/webhook", tags=["Webhook"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])

@app.get("/")
def read_root():
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
