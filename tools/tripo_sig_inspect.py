import inspect
from tripo3d import TripoClient
import os
c = TripoClient(os.environ.get('TRIPO_API_KEY'))
for fname in ('image_to_model','create_task','text_to_model'):
    fn = getattr(c,fname)
    try:
        print(fname, 'signature:', inspect.signature(fn))
    except Exception as e:
        print(fname, 'sig error', e)
