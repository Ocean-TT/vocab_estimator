from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIR
from backend.database import Base, engine
from backend.routers import batch, test, text, cat

# 启动时自动建表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="English Vocabulary Estimator",
    description="基于分层抽样与IRT自适应测试的英语词汇量估算工具",
    version="1.0.0",
)

# 开发期放开跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由：基础测试、批量估算、文本分析、CAT自适应测试
app.include_router(test.router)
app.include_router(batch.router)
app.include_router(text.router)
app.include_router(cat.router)

# 挂载前端静态文件
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "API is running. Frontend not found."}


@app.get("/health")
def health():
    return {"status": "ok"}
