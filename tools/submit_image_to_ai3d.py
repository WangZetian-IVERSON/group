#!/usr/bin/env python3
"""提交仓库内图片到 Tencent AI3D (SubmitHunyuanTo3DProJob) 并轮询查询直到完成。

使用方法:
- 确保安装 SDK: pip install tencentcloud-sdk-python
- 在运行前设置环境变量: TENCENTCLOUD_SECRET_ID, TENCENTCLOUD_SECRET_KEY
- 运行: python tools/submit_image_to_ai3d.py

脚本会把结果保存到 `tools/ai3d_last_job.json`。
"""
import os
import json
import time
import datetime
import sys
from typing import Optional
import traceback
import hashlib
import math
from pathlib import Path

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ai3d.v20250513 import ai3d_client, models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException


ROOT = Path(__file__).resolve().parent.parent
# Allow overriding the image path via environment variable `AI3D_IMAGE_PATH`
IMAGE_PATH = Path(os.getenv('AI3D_IMAGE_PATH', str(ROOT / 'generated_floorplan_colored.png')))
OUT_PATH = Path(__file__).resolve().parent / 'ai3d_last_job.json'
CACHE_PATH = Path(__file__).resolve().parent / 'ai3d_cache.json'


def encode_image_to_base64(path: Path) -> str:
    import base64
    with open(path, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode('utf-8')


def submit_image(secret_id, secret_key, region='ap-guangzhou'):
    cred = credential.Credential(secret_id, secret_key)
    httpProfile = HttpProfile()
    httpProfile.endpoint = 'ai3d.tencentcloudapi.com'
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    client = ai3d_client.Ai3dClient(cred, region, clientProfile)

    req = models.SubmitHunyuanTo3DProJobRequest()

    img_b64 = encode_image_to_base64(IMAGE_PATH)
    # 支持通过环境变量控制是否只上传图片
    only_image = os.getenv('ONLY_IMAGE', '0') == '1'
    prompt_text = os.getenv('AI3D_PROMPT')
    params = {'ImageBase64': img_b64}
    # 若未设置 ONLY_IMAGE，则尝试从环境变量取 Prompt；否则只上传图片
    if not only_image and prompt_text:
        params['Prompt'] = prompt_text
    req.from_json_string(json.dumps(params))

    return client.SubmitHunyuanTo3DProJob(req)


def query_job(secret_id, secret_key, job_id, region='ap-guangzhou'):
    cred = credential.Credential(secret_id, secret_key)
    httpProfile = HttpProfile()
    httpProfile.endpoint = 'ai3d.tencentcloudapi.com'
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    client = ai3d_client.Ai3dClient(cred, region, clientProfile)

    qreq = models.QueryHunyuanTo3DProJobRequest()
    qreq.from_json_string(json.dumps({'JobId': job_id}))
    return client.QueryHunyuanTo3DProJob(qreq)


def main():
    secret_id = os.getenv('TENCENTCLOUD_SECRET_ID')
    secret_key = os.getenv('TENCENTCLOUD_SECRET_KEY')
    # Prefer an explicit env var if set; otherwise default to ap-guangzhou
    env_region = os.environ.get('TENCENTCLOUD_REGION')
    region = env_region if env_region else 'ap-guangzhou'

    if not secret_id or not secret_key:
        print('请先设置环境变量 TENCENTCLOUD_SECRET_ID 和 TENCENTCLOUD_SECRET_KEY')
        return

    if not IMAGE_PATH.exists():
        print('找不到图片:', IMAGE_PATH)
        return

    result_record = {'submit': None, 'poll': []}

    # load cache (optional) to estimate typical job duration and preferred region
    cache = {}
    try:
        if CACHE_PATH.exists():
            cache = json.loads(CACHE_PATH.read_text(encoding='utf-8'))
    except Exception:
        cache = {}

    # If user did not explicitly set TENCENTCLOUD_REGION, prefer cached region
    try:
        if not env_region and isinstance(cache, dict):
            cached_region = cache.get('region')
            if cached_region:
                print(f'未检测到显式 region 环境变量，使用缓存的 region: {cached_region}')
                region = cached_region
    except Exception:
        pass

    try:
        print('提交图片到 Ai3d（region=' + region + '）...')
        submit_time = time.time()
        submit_resp = submit_image(secret_id, secret_key, region=region)
        submit_json = json.loads(submit_resp.to_json_string())
        print('提交返回:', submit_json)
        result_record['submit'] = submit_json

        job_id = submit_json.get('JobId') or submit_json.get('JobID')
        if not job_id:
            print('提交响应中未包含 JobId，结束。')
            OUT_PATH.write_text(json.dumps(result_record, ensure_ascii=False, indent=2))
            return

        print('得到 JobId:', job_id)

        # 轮询查询
        max_attempts = 120  # e.g., 10 minutes if 5s sleep
        poll_interval = 5

        # If we have a cached typical duration for jobs, wait that duration * 0.8
        # before starting frequent polling to reduce the number of queries. Also
        # compute a starting attempt index so logs don't begin at 1 after waiting.
        initial_wait = 0
        try:
            est = None
            if isinstance(cache, dict):
                est = cache.get('last_job_duration_seconds')
            if est and isinstance(est, (int, float)) and est > 0:
                initial_wait = max(2, int(est * 0.8))
                print(f'根据缓存，首次轮询前先等待 {initial_wait} 秒以节省查询。')
                time.sleep(initial_wait)
        except Exception:
            initial_wait = 0

        # Determine starting attempt index so logs are closer to the actual progress
        attempt = max(1, int(initial_wait / poll_interval))

        # Choose which region to use for queries. Start with the region used for
        # submission, but prefer cached region if user didn't explicitly set one.
        query_region = region
        cached_region = None
        try:
            if isinstance(cache, dict):
                cached_region = cache.get('region')
                # if user didn't set region explicitly and cache has a region, prefer it
                # (we handled this above for submission, but keep here for clarity)
                if not env_region and cached_region:
                    query_region = cached_region
        except Exception:
            cached_region = None

        consecutive_errors = 0

        while attempt < max_attempts:
            attempt += 1
            try:
                qresp = query_job(secret_id, secret_key, job_id, region=query_region)
                qjson = json.loads(qresp.to_json_string())
                print(f'[{attempt}] 查询返回:', qjson)
                result_record['poll'].append(qjson)

                # 尝试判断状态字段
                status = None
                if isinstance(qjson, dict):
                    # common possible fields
                    for k in ('Status', 'JobStatus', 'State'):
                        if k in qjson:
                            status = qjson[k]
                            break
                    # sometimes nested under Response
                    if status is None and 'Response' in qjson:
                        resp = qjson['Response']
                        for k in ('Status', 'JobStatus', 'State'):
                            if k in resp:
                                status = resp[k]
                                break

                if status:
                    status_str = str(status).upper()
                    # treat DONE as a successful terminal state as well
                    if status_str in ('SUCCESS', 'COMPLETED', 'SUCCEEDED', 'DONE'):
                        print('任务完成:', status_str)
                        # write cache: duration from submit to first success
                        try:
                            duration = time.time() - submit_time
                            cache_out = {
                                'region': region,
                                'last_job_id': job_id,
                                'last_job_duration_seconds': duration,
                                'last_success_time': datetime.datetime.utcnow().isoformat() + 'Z'
                            }
                            CACHE_PATH.write_text(json.dumps(cache_out, ensure_ascii=False, indent=2), encoding='utf-8')
                        except Exception:
                            print('缓存写入失败：', traceback.format_exc())
                        break
                    if status_str in ('FAILED', 'ERROR'):
                        print('任务失败:', status_str)
                        break

            except TencentCloudSDKException as e:
                err_str = str(e)
                print('查询异常:', type(e).__name__, err_str)
                result_record['poll'].append({'error': err_str})
                consecutive_errors += 1
                # If the error indicates unsupported region, try switching to cached region
                if cached_region and cached_region != query_region and ('UnsupportedRegion' in err_str or 'unsupported region' in err_str.lower()):
                    print(f'检测到区域不支持错误，尝试切换查询 region -> {cached_region}')
                    query_region = cached_region
                    # do not sleep extra here, immediately retry in next loop iteration
                    continue
                # if we see several consecutive errors, and we have a cached_region,
                # attempt switching to it once
                if consecutive_errors >= 3 and cached_region and cached_region != query_region:
                    print(f'连续错误 {consecutive_errors} 次，切换查询 region -> {cached_region}')
                    query_region = cached_region
                    consecutive_errors = 0

            time.sleep(poll_interval)

    except TencentCloudSDKException as e:
        print('提交异常:', type(e).__name__, str(e))
        result_record['submit'] = {'error': str(e)}
    except Exception as e:
        print('其它异常:', type(e).__name__, str(e))
        result_record['submit'] = {'error': str(e)}

    OUT_PATH.write_text(json.dumps(result_record, ensure_ascii=False, indent=2))
    print('全部结果已保存到', OUT_PATH)


if __name__ == '__main__':
    main()
