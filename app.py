#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
import subprocess
import json
import os
import re

app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <h1>Docker镜像大小查询服务</h1>
    <p>使用方法: /image-info?image=镜像名:标签</p>
    <p>例如: <a href="/image-info?image=nginx:latest">/image-info?image=nginx:latest</a></p>
    '''

@app.route('/image-info')
def image_info():
    # 获取请求参数
    image = request.args.get('image', '')
    if not image:
        return jsonify({
            'status': 'error',
            'message': '请提供镜像名称，例如：/image-info?image=nginx:latest'
        }), 400
    
    # 检查镜像名是否带标签，未带则补全为:latest
    if ':' not in image:
        image = f"{image}:latest"
    
    # 获取认证信息（可选）
    username = request.args.get('username') or os.environ.get('IMAGE_USERNAME', '')
    password = request.args.get('password') or os.environ.get('IMAGE_PASSWORD', '')
    creds = []
    if username and password:
        creds = ['--creds', f'{username}:{password}']
    
    # 获取代理信息（可选）
    proxy = request.args.get('proxy') or os.environ.get('HTTPS_PROXY', '')
    env = os.environ.copy()
    if proxy:
        env['HTTPS_PROXY'] = proxy
    
    try:
        # 调用skopeo获取镜像信息
        cmd = ['skopeo', 'inspect']
        cmd.extend(creds)
        cmd.append(f'docker://{image}')
        
        process = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            # 检查常见错误
            err = process.stderr.lower()
            if any(msg in err for msg in ['unauthorized', 'forbidden', 'not found']):
                return jsonify({
                    'status': 'error',
                    'message': f'权限不足或镜像不存在: {image}',
                    'error': process.stderr
                }), 404
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'获取镜像信息失败: {image}',
                    'error': process.stderr
                }), 500
        
        # 解析JSON结果
        result = json.loads(process.stdout)
        
        # 提取层信息
        layersData = result.get('LayersData', [])
        
        # 计算压缩和未压缩大小
        compressed_size = sum(layer.get('Size', 0) for layer in layersData)
        uncompressed_size = sum(layer.get('UncompressedSize', 0) for layer in layersData if 'UncompressedSize' in layer)
        
        # 计算人类可读格式
        compressed_mb = compressed_size / 1024 / 1024
        
        response = {
            'status': 'success',
            'image': image,
            'compressed_size': compressed_size,
            'compressed_size_mb': round(compressed_mb, 2),
            'raw_data': result
        }
        
        # 如果有未压缩大小，添加到响应
        if uncompressed_size > 0:
            uncompressed_mb = uncompressed_size / 1024 / 1024
            response['uncompressed_size'] = uncompressed_size
            response['uncompressed_size_mb'] = round(uncompressed_mb, 2)
        else:
            # 估算未压缩大小（乘以1.7，与原脚本一致）
            estimated_uncompressed = compressed_size * 1.7
            estimated_uncompressed_mb = estimated_uncompressed / 1024 / 1024
            response['estimated_uncompressed_size'] = estimated_uncompressed
            response['estimated_uncompressed_size_mb'] = round(estimated_uncompressed_mb, 2)
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'处理异常: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000) 