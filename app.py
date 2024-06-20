import os
import json
import aiofiles
import uvicorn
from src.helper import qa_generator
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Form, Request, Response, File

app = FastAPI()
app.mount("/output", StaticFiles(directory="output"), name="output")

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def chat(request: Request, pdf_file: bytes = File(), filename: str = Form(...)):
    pdf_filename = os.path.join( 'output/', filename)

    async with aiofiles.open(pdf_filename, 'wb') as f:
        await f.write(pdf_file)
 
    response_data = jsonable_encoder(json.dumps({"msg": 'success',"pdf_filename": pdf_filename}))
    res = Response(response_data)
    return res

@app.post("/analyze")
async def chat(request: Request, pdf_filename: str = Form(...)):

    output_file = qa_generator(pdf_filename)
    response_data = jsonable_encoder(json.dumps({"output_file": output_file}))
    res = Response(response_data)
    
    return res


if __name__ == "__main__":
    uvicorn.run("app:app", host='0.0.0.0', port=8080, reload=True)
