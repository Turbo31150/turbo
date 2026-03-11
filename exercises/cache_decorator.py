from functools import wraps

def cache_with_ttl(ttl):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get current time
            current_time = datetime.datetime.now()
            # Calculate expiration time
            expiration_time = current_time + datetime.timedelta(seconds=ttl)
            # Check if the cache is expired
            if datetime.datetime.now() > expiration_time:
                # If expired, delete the cache
                # (This is a simplified example; in practice, you would store the cache in a database)
                print(f'Cache expired at {expiration_time}
')
                return func(*args, **kwargs)
            
            # If not expired, return the cached result
            print(f'Cache not expired at {expiration_time}
')
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Example usage
@cache_with_ttl(60)
def get_data():
    return 'Cached data'

print(get_data())