#!/usr/bin/env python3
"""尝试在多个 region 上用 Tencent Cloud Python SDK 调用 Ai3d 的 SubmitHunyuanTo3DProJob。

会读取环境变量：TENCENTCLOUD_SECRET_ID, TENCENTCLOUD_SECRET_KEY
输出会打印每个 region 的结果，并保存到 tools/ai3d_region_test_results.json
"""
import os
import json
import time
from pathlib import Path

try:
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.ai3d.v20250513 import ai3d_client, models
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
except Exception as e:
    print('缺少 tencentcloud SDK，先安装: pip install tencentcloud-sdk-python')
    raise


REGIONS = [
    'ap-guangzhou',
    'ap-shanghai',
    'ap-beijing',
    'ap-shenzhen',
    'ap-chengdu',
    'ap-hongkong',
]

OUT_PATH = Path(__file__).resolve().parent / 'ai3d_region_test_results.json'


def try_region(secret_id, secret_key, region):
    cred = credential.Credential(secret_id, secret_key)
    httpProfile = HttpProfile()
    httpProfile.endpoint = 'ai3d.tencentcloudapi.com'
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    client = ai3d_client.Ai3dClient(cred, region, clientProfile)

    # 构造最小请求，使用 JSON 填充以避免属性差异
    req = models.SubmitHunyuanTo3DProJobRequest()
    params = {
        "Prompt": "Test: tiny 3D thumbnail - abstract",
    }
    req.from_json_string(json.dumps(params))

    try:
        resp = client.SubmitHunyuanTo3DProJob(req)
        return {'success': True, 'response': json.loads(resp.to_json_string())}
    except TencentCloudSDKException as e:
        # SDK 异常，包含 code/message
        return {'success': False, 'error': {'code': getattr(e, 'code', None), 'message': str(e)}}
    except Exception as e:
        return {'success': False, 'error': {'code': None, 'message': str(e)}}


def main():
    secret_id = os.getenv('TENCENTCLOUD_SECRET_ID')
    secret_key = os.getenv('TENCENTCLOUD_SECRET_KEY')
    if not secret_id or not secret_key:
        print('请先设置环境变量 TENCENTCLOUD_SECRET_ID 和 TENCENTCLOUD_SECRET_KEY')
        return

    results = {}
    for r in REGIONS:
        print(f'尝试 region: {r} ...')
        res = try_region(secret_id, secret_key, r)
        results[r] = res
        if res.get('success'):
            print(f'  成功: 返回 keys = {list(res["response"].keys())}')
        else:
            err = res.get('error') or {}
            print(f'  失败: code={err.get("code")} message={err.get("message")[:200]}')
        # 小间隔，避免触发速率限制
        time.sleep(1)

    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print('已把结果保存到', OUT_PATH)


if __name__ == '__main__':
    main()
