#!/usr/bin/env python3
"""示例：使用 Tencent Cloud Python SDK 调用混元生3D (Ai3dClient)

说明:
- 不会自动运行任何生成任务；脚本示例演示如何构造请求并发送。
- 请先在环境中设置 `TENCENTCLOUD_SECRET_ID` 和 `TENCENTCLOUD_SECRET_KEY`，或在代码中显式填充（不推荐）。
- 安装依赖: `pip install tencentcloud-sdk-python`
"""
import os
import json
import sys

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ai3d.v20250513 import ai3d_client, models


def main():
    secret_id = os.getenv('TENCENTCLOUD_SECRET_ID')
    secret_key = os.getenv('TENCENTCLOUD_SECRET_KEY')
    region = os.getenv('TENCENTCLOUD_REGION', 'ap-shanghai')

    if not secret_id or not secret_key:
        print('请先设置环境变量 TENCENTCLOUD_SECRET_ID 和 TENCENTCLOUD_SECRET_KEY')
        sys.exit(2)

    cred = credential.Credential(secret_id, secret_key)
    httpProfile = HttpProfile()
    httpProfile.endpoint = "ai3d.tencentcloudapi.com"

    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile

    client = ai3d_client.Ai3dClient(cred, region, clientProfile)

    # 示例：提交一个 Pro 任务（字段名请根据官方文档或 SDK models 调整）
    submit_req = models.SubmitHunyuanTo3DProJobRequest()

    # 以下 params 是示例结构，务必参照官方 API 文档填写正确字段
    params = {
        "Prompt": "A low-poly stylized chair, simple shapes, neutral colors",
        # 可能的其它字段示例："Mode": "pro", "Quality": "high", "RenderConfig": {...}
    }
    submit_req.from_json_string(json.dumps(params))

    print('提交任务中...')
    try:
        submit_resp = client.SubmitHunyuanTo3DProJob(submit_req)
        print('提交返回:')
        print(submit_resp.to_json_string())
    except Exception as e:
        print('提交任务时出错:', type(e).__name__, str(e))
        sys.exit(1)

    # 如果返回包含 JobId，你可以使用 Query 接口查询任务状态，示例如下（注释掉，按需解开）:
    # job_id = '<从 submit_resp 中提取 JobId>'
    # qreq = models.QueryHunyuanTo3DProJobRequest()
    # qreq.from_json_string(json.dumps({"JobId": job_id}))
    # qresp = client.QueryHunyuanTo3DProJob(qreq)
    # print('查询返回:')
    # print(qresp.to_json_string())


if __name__ == '__main__':
    main()
