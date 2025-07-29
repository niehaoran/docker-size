#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
import subprocess
import json
import os
import re
import logging
import traceback
import sys

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('docker-size')

app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <h1>Docker镜像大小查询服务</h1>
    <p>使用方法: /image-info?image=镜像名:标签</p>
    <p>例如: <a href="/image-info?image=nginx:latest">/image-info?image=nginx:latest</a></p>
    <p>仅查询大小: <a href="/image-size?image=nginx:latest">/image-size?image=nginx:latest</a></p>
    '''

def get_image_data(image, username=None, password=None, proxy=None):
    """获取镜像数据的通用函数"""
    # 检查镜像名是否带标签，未带则补全为:latest
    if ':' not in image:
        image = f"{image}:latest"
        logger.info(f"镜像未指定标签，补全为: {image}")
    
    # 获取认证信息（可选）
    username = username or os.environ.get('IMAGE_USERNAME', '')
    password = password or os.environ.get('IMAGE_PASSWORD', '')
    creds = []
    if username and password:
        creds = ['--creds', f'{username}:{password}']
        logger.info(f"使用认证信息: 用户名={username}")
    
    # 获取代理信息（可选）
    proxy = proxy or os.environ.get('HTTPS_PROXY', '')
    env = os.environ.copy()
    if proxy:
        env['HTTPS_PROXY'] = proxy
        # 也设置HTTP_PROXY，增加兼容性
        env['HTTP_PROXY'] = proxy
        logger.info(f"使用代理: {proxy}")
    
    # 调用skopeo获取镜像信息
    cmd = ['skopeo', 'inspect']
    cmd.extend(creds)
    cmd.append(f'docker://{image}')
    
    logger.info(f"执行命令: {' '.join(cmd)}")
    
    process = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True
    )
    
    if process.returncode != 0:
        # 详细记录错误信息
        logger.error(f"skopeo命令执行失败，返回码: {process.returncode}")
        logger.error(f"错误输出: {process.stderr}")
        
        # 检查常见错误
        err = process.stderr.lower()
        if any(msg in err for msg in ['unauthorized', 'forbidden', 'not found']):
            logger.error(f"权限不足或镜像不存在: {image}")
            return {
                'status': 'error',
                'code': 404,
                'message': f'权限不足或镜像不存在: {image}',
                'error': process.stderr,
                'command': ' '.join(cmd)
            }
        else:
            logger.error(f"获取镜像信息失败: {image}")
            return {
                'status': 'error',
                'code': 500,
                'message': f'获取镜像信息失败: {image}',
                'error': process.stderr,
                'command': ' '.join(cmd)
            }
    
    # 解析JSON结果
    result = json.loads(process.stdout)
    logger.info(f"成功获取镜像信息: {image}")
    
    return {
        'status': 'success',
        'result': result
    }

def calculate_image_size(result):
    """计算镜像大小的辅助函数"""
    # 提取层信息，如果不存在，记录日志并返回0
    layers_data = result.get('LayersData', [])
    
    if not layers_data:
        logger.warning("没有找到LayersData字段，尝试其他方法计算大小...")
        # 尝试从config.history中获取大小（某些skopeo版本可能使用这种格式）
        if 'config' in result and 'history' in result['config']:
            logger.debug("尝试从config.history计算大小")
            # 这里可以添加备选的计算逻辑
    
    # 打印原始数据，帮助调试
    logger.debug(f"原始镜像数据: {json.dumps(result, indent=2)}")
    
    # 计算压缩大小
    compressed_size = 0
    for layer in layers_data:
        layer_size = layer.get('Size', 0)
        logger.debug(f"图层大小: {layer_size}")
        compressed_size += layer_size
    
    # 计算未压缩大小
    uncompressed_size = 0
    for layer in layers_data:
        if 'UncompressedSize' in layer:
            uncompressed_size += layer.get('UncompressedSize', 0)
    
    # 如果未压缩大小为0，尝试从其他字段获取
    if uncompressed_size == 0 and compressed_size > 0:
        # 查看是否有其他字段包含未压缩大小信息
        for layer in layers_data:
            for key, value in layer.items():
                if 'uncompressed' in key.lower() and isinstance(value, (int, float)) and value > 0:
                    logger.debug(f"从{key}字段找到未压缩大小: {value}")
                    uncompressed_size += value
    
    return compressed_size, uncompressed_size

@app.route('/image-size')
def image_size():
    """仅返回镜像压缩大小和预估实际大小的API端点"""
    # 获取请求参数
    image = request.args.get('image', '')
    if not image:
        return jsonify({
            'status': 'error',
            'message': '请提供镜像名称，例如：/image-size?image=nginx:latest'
        }), 400
    
    logger.info(f"开始处理镜像大小请求: {image}")
    
    try:
        # 获取可选参数
        username = request.args.get('username')
        password = request.args.get('password')
        proxy = request.args.get('proxy')
        
        # 调用共用函数获取镜像数据
        data = get_image_data(image, username, password, proxy)
        
        # 检查是否出错
        if data['status'] == 'error':
            return jsonify({
                'status': 'error',
                'message': data['message'],
                'error': data.get('error')
            }), data['code']
        
        # 从结果中计算大小
        result = data['result']
        compressed_size, uncompressed_size = calculate_image_size(result)
        
        # 计算人类可读格式
        compressed_mb = compressed_size / 1024 / 1024
        
        logger.info(f"镜像 {image} 压缩大小: {compressed_mb:.2f}MB")
        
        response = {
            'status': 'success',
            'image': image,
            'compressed_size': compressed_size,
            'compressed_size_mb': round(compressed_mb, 2)
        }
        
        # 如果有未压缩大小，添加到响应
        if uncompressed_size > 0:
            uncompressed_mb = uncompressed_size / 1024 / 1024
            response['uncompressed_size'] = uncompressed_size
            response['uncompressed_size_mb'] = round(uncompressed_mb, 2)
            logger.info(f"镜像 {image} 未压缩大小: {uncompressed_mb:.2f}MB")
        else:
            # 估算未压缩大小（乘以1.7，与原脚本一致）
            estimated_uncompressed = compressed_size * 1.7
            estimated_uncompressed_mb = estimated_uncompressed / 1024 / 1024
            response['estimated_uncompressed_size'] = estimated_uncompressed
            response['estimated_uncompressed_size_mb'] = round(estimated_uncompressed_mb, 2)
            logger.info(f"镜像 {image} 估算未压缩大小: {estimated_uncompressed_mb:.2f}MB")
        
        return jsonify(response)
        
    except Exception as e:
        # 捕获并记录所有异常，包括堆栈跟踪
        error_traceback = traceback.format_exc()
        logger.error(f"处理异常: {str(e)}")
        logger.error(f"详细堆栈: {error_traceback}")
        
        return jsonify({
            'status': 'error',
            'message': f'处理异常: {str(e)}'
        }), 500

@app.route('/image-info')
def image_info():
    # 获取请求参数
    image = request.args.get('image', '')
    if not image:
        return jsonify({
            'status': 'error',
            'message': '请提供镜像名称，例如：/image-info?image=nginx:latest'
        }), 400
    
    logger.info(f"开始处理镜像请求: {image}")
    
    try:
        # 获取可选参数
        username = request.args.get('username')
        password = request.args.get('password')
        proxy = request.args.get('proxy')
        
        # 调用共用函数获取镜像数据
        data = get_image_data(image, username, password, proxy)
        
        # 检查是否出错
        if data['status'] == 'error':
            return jsonify({
                'status': 'error',
                'message': data['message'],
                'error': data.get('error')
            }), data['code']
        
        # 从结果中计算大小
        result = data['result']
        compressed_size, uncompressed_size = calculate_image_size(result)
        
        # 计算人类可读格式
        compressed_mb = compressed_size / 1024 / 1024
        
        logger.info(f"镜像 {image} 压缩大小: {compressed_mb:.2f}MB")
        
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
            logger.info(f"镜像 {image} 未压缩大小: {uncompressed_mb:.2f}MB")
        else:
            # 估算未压缩大小（乘以1.7，与原脚本一致）
            estimated_uncompressed = compressed_size * 1.7
            estimated_uncompressed_mb = estimated_uncompressed / 1024 / 1024
            response['estimated_uncompressed_size'] = estimated_uncompressed
            response['estimated_uncompressed_size_mb'] = round(estimated_uncompressed_mb, 2)
            logger.info(f"镜像 {image} 估算未压缩大小: {estimated_uncompressed_mb:.2f}MB")
        
        return jsonify(response)
        
    except Exception as e:
        # 捕获并记录所有异常，包括堆栈跟踪
        error_traceback = traceback.format_exc()
        logger.error(f"处理异常: {str(e)}")
        logger.error(f"详细堆栈: {error_traceback}")
        
        return jsonify({
            'status': 'error',
            'message': f'处理异常: {str(e)}',
            'traceback': error_traceback
        }), 500

if __name__ == '__main__':
    # 打印启动信息
    logger.info("Docker镜像大小查询服务启动中...")
    
    app.run(host='0.0.0.0', port=8000) 