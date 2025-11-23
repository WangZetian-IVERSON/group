import os
import asyncio

key = os.environ.get('TRIPO_API_KEY')
print('Key present:', bool(key))
try:
    from tripo3d import TripoClient
    print('Imported tripo3d')
    try:
        client = TripoClient(key)
        print('Instantiated TripoClient:', client)
    except Exception as e:
        print('Instantiate error:', repr(e))
        try:
            from tripo3d.client_impl import ClientImpl
            print('Imported ClientImpl')
            cli = ClientImpl(key, 'https://api.tripo3d.ai/v2/openapi')
            print('ClientImpl instantiated:', cli)
        except Exception as e2:
            print('ClientImpl error:', repr(e2))
except Exception as e:
    print('Import error:', repr(e))
