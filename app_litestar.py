from litestar import Litestar, get

@get("/")
def hello_world() -> dict:
    return {"message": "Hello World"}

@get("/hello/{name:str}")
def hello_name(name: str) -> dict:
    return {"message": f"Hello, {name}!"}

app = Litestar(route_handlers=[hello_world, hello_name])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_litestar:app", host="127.0.0.1", port=8000, reload=True)
