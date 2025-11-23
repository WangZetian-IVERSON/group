import inspect
from tripo3d import TripoClient
import os
key = os.environ.get('TRIPO_API_KEY')
client = TripoClient(key)
print('Client type:', type(client))
for name in dir(client):
    if name.startswith('_'):
        continue
    attr = getattr(client, name)
    if inspect.iscoroutinefunction(attr):
        kind = 'coroutine'
    elif inspect.isfunction(attr) or inspect.ismethod(attr):
        kind = 'callable'
    else:
        kind = type(attr).__name__
    print(f"{name}: {kind}")
