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
from pathlib import Path

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ai3d.v20250513 import ai3d_client, models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException


ROOT = Path(__file__).resolve().parent.parent
IMAGE_PATH = ROOT / 'generated_floorplan_colored.png'
OUT_PATH = Path(__file__).resolve().parent / 'ai3d_last_job.json'


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
    region = os.getenv('TENCENTCLOUD_REGION', 'ap-guangzhou')

    if not secret_id or not secret_key:
        print('请先设置环境变量 TENCENTCLOUD_SECRET_ID 和 TENCENTCLOUD_SECRET_KEY')
        return

    if not IMAGE_PATH.exists():
        print('找不到图片:', IMAGE_PATH)
        return

    result_record = {'submit': None, 'poll': []}

    try:
        print('提交图片到 Ai3d（region=' + region + '）...')
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
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                qresp = query_job(secret_id, secret_key, job_id, region=region)
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
                    if status_str in ('SUCCESS', 'COMPLETED', 'SUCCEEDED'):
                        print('任务完成:', status_str)
                        break
                    if status_str in ('FAILED', 'ERROR'):
                        print('任务失败:', status_str)
                        break

            except TencentCloudSDKException as e:
                print('查询异常:', type(e).__name__, str(e))
                result_record['poll'].append({'error': str(e)})

            time.sleep(5)

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
