#!/usr/bin/env python3
"""Helper to submit an image to Tencent Hunyuan AI3D and download resulting artifacts.

Provides a synchronous function `submit_and_download` that returns a list of saved file paths.
"""
from pathlib import Path
import time
import json
import base64
import requests

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ai3d.v20250513 import ai3d_client, models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode('utf-8')


def _download_url(url: str, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    # choose filename from url
    fname = url.split('?')[0].split('/')[-1]
    outpath = outdir / fname
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    outpath.write_bytes(r.content)
    return outpath


def submit_and_download(image_path: str, secret_id: str, secret_key: str, region: str = 'ap-guangzhou', outdir: str = None, only_image: bool = True, poll_interval: int = 5, max_attempts: int = 240):
    """Submit image and wait for job completion, then download artifacts.

    Returns: dict with keys: job_id, status, files (list of saved Path strings), raw_response (last query json)
    """
    img_p = Path(image_path)
    if not img_p.exists():
        raise FileNotFoundError(str(img_p))

    cred = credential.Credential(secret_id, secret_key)
    httpProfile = HttpProfile()
    httpProfile.endpoint = 'ai3d.tencentcloudapi.com'
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    client = ai3d_client.Ai3dClient(cred, region, clientProfile)

    req = models.SubmitHunyuanTo3DProJobRequest()
    params = {'ImageBase64': _encode_image(img_p)}
    if not only_image:
        # leave Prompt empty by default; caller may set environment if needed
        pass
    req.from_json_string(json.dumps(params))

    submit_resp = client.SubmitHunyuanTo3DProJob(req)
    submit_json = json.loads(submit_resp.to_json_string())
    job_id = submit_json.get('JobId') or submit_json.get('JobID')
    start_time = time.time()

    last_q = None
    for attempt in range(1, max_attempts + 1):
        time.sleep(poll_interval)
        try:
            qreq = models.QueryHunyuanTo3DProJobRequest()
            qreq.from_json_string(json.dumps({'JobId': job_id}))
            qresp = client.QueryHunyuanTo3DProJob(qreq)
            qjson = json.loads(qresp.to_json_string())
            last_q = qjson
            # find status
            status = None
            for k in ('Status', 'JobStatus', 'State'):
                if k in qjson:
                    status = qjson[k]
                    break
            if status is None and 'Response' in qjson:
                resp = qjson['Response']
                for k in ('Status', 'JobStatus', 'State'):
                    if k in resp:
                        status = resp[k]
                        break

            if status:
                s = str(status).upper()
                if s in ('SUCCESS', 'COMPLETED', 'SUCCEEDED', 'DONE'):
                    # collect ResultFile3Ds
                    files = []
                    # The structure may vary; search for ResultFile3Ds
                    candidates = []
                    if 'ResultFile3Ds' in qjson:
                        candidates = qjson['ResultFile3Ds']
                    elif 'Response' in qjson and 'ResultFile3Ds' in qjson['Response']:
                        candidates = qjson['Response']['ResultFile3Ds']
                    else:
                        # try nested keys
                        for v in qjson.values():
                            if isinstance(v, dict) and 'ResultFile3Ds' in v:
                                candidates = v['ResultFile3Ds']
                                break

                    out_paths = []
                    od = Path(outdir) if outdir else (Path(__file__).resolve().parent / 'ai3d_outputs' / job_id)
                    od.mkdir(parents=True, exist_ok=True)
                    for item in candidates or []:
                        try:
                            url = item.get('Url') or item.get('url')
                            if not url:
                                continue
                            saved = _download_url(url, od)
                            out_paths.append(str(saved))
                        except Exception:
                            continue

                    return {'job_id': job_id, 'status': 'DONE', 'files': out_paths, 'raw_response': last_q}
                if s in ('FAILED', 'ERROR'):
                    return {'job_id': job_id, 'status': 'FAILED', 'files': [], 'raw_response': last_q}
        except TencentCloudSDKException as e:
            # try again
            last_q = {'error': str(e)}
            continue
    # timeout
    return {'job_id': job_id, 'status': 'TIMEOUT', 'files': [], 'raw_response': last_q}


if __name__ == '__main__':
    import os
    import sys
    img = sys.argv[1] if len(sys.argv) > 1 else None
    sid = os.environ.get('TENCENTCLOUD_SECRET_ID')
    sk = os.environ.get('TENCENTCLOUD_SECRET_KEY')
    if not img or not sid or not sk:
        print('Usage: submit_tencent_ai3d.py <image_path> (requires TENCENTCLOUD_SECRET_ID/KEY env)')
        raise SystemExit(2)
    r = submit_and_download(img, sid, sk)
    print(json.dumps(r, indent=2, ensure_ascii=False))
