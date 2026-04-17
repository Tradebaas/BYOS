import uvicorn
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=False)
