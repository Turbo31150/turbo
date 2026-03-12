import time;
def decorate(f): def wrapper(*args, **kwargs): start = time.time(); f(*args, **kwargs); end = time.time(); print(f'{f.__name__} took {end - start:.4f} seconds'); return wrapper;