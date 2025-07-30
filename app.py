#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, abort
import subprocess
import json
import os
import re
import logging
import traceback
import sys
import functools
import time
from flask_caching import Cache

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

# 配置缓存
cache_config = {
    "CACHE_TYPE": os.environ.get("CACHE_TYPE", "simple"),  # 默认使用简单内存缓存
    "CACHE_DEFAULT_TIMEOUT": int(os.environ.get("CACHE_TIMEOUT", 3600)),  # 默认缓存1小时
}

# 如果设置了Redis缓存
if os.environ.get("CACHE_REDIS_URL"):
    cache_config["CACHE_REDIS_URL"] = os.environ.get("CACHE_REDIS_URL")

cache = Cache(config=cache_config)
cache.init_app(app)

# 日志输出缓存配置
logger = logging.getLogger('docker-size')
logger.info(f"缓存类型: {cache_config['CACHE_TYPE']}")
logger.info(f"缓存超时: {cache_config['CACHE_DEFAULT_TIMEOUT']}秒")

# 读取API认证密码
API_KEY = os.environ.get('API_KEY', '')
logger.info(f"API认证{'已配置' if API_KEY else '未配置'}")

# API认证装饰器
def require_api_key(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # 如果没有设置API_KEY，则不进行认证
        if not API_KEY:
            return f(*args, **kwargs)
        
        # 从请求中获取api_key
        api_key = request.args.get('api_key', '')
        
        # 验证API密钥
        if api_key != API_KEY:
            logger.warning(f"API认证失败: 提供的API密钥不正确")
            return jsonify({
                'status': 'error',
                'message': 'API认证失败: 无效的API密钥'
            }), 401
            
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    api_info = "需要API密钥进行认证" if API_KEY else "无需认证"
    api_param = "&api_key=您的API密钥" if API_KEY else ""
    
    return f'''
    <h1>Docker镜像大小查询服务</h1>
    <p>使用方法: /image-info?image=镜像名:标签{api_param}</p>
    <p>例如: <a href="/image-info?image=nginx:latest{api_param}">/image-info?image=nginx:latest</a></p>
    <p>仅查询大小: <a href="/image-size?image=nginx:latest{api_param}">/image-size?image=nginx:latest</a></p>
    <p>API认证: {api_info}</p>
    <hr>
    <h2>缓存信息</h2>
    <p>缓存类型: {cache_config["CACHE_TYPE"]}</p>
    <p>缓存超时: {cache_config["CACHE_DEFAULT_TIMEOUT"]}秒</p>
    <p>缓存状态: <a href="/cache-info{api_param}">查看缓存状态</a></p>
    <p>清除缓存: <a href="/cache-clear{api_param}">清除所有缓存</a></p>
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

def make_cache_key():
    """生成缓存键的函数，考虑所有相关的请求参数"""
    # 基本参数
    image = request.args.get('image', '')
    username = request.args.get('username', os.environ.get('IMAGE_USERNAME', ''))
    password = request.args.get('password', os.environ.get('IMAGE_PASSWORD', ''))
    proxy = request.args.get('proxy', os.environ.get('HTTPS_PROXY', ''))
    
    # 组合生成唯一键
    key_parts = [
        f"image:{image}",
        f"username:{username}",  # 用户名会影响结果
        # 不包含密码在缓存键中，因为相同用户名下，密码通常一致
        f"proxy:{proxy}",  # 代理可能影响结果
    ]
    
    # 生成唯一缓存键
    return "|".join(key_parts)

def calculate_image_size(result):
    """计算镜像大小的辅助函数"""
    # 打印原始数据，帮助调试
    logger.debug(f"原始镜像数据: {json.dumps(result, indent=2)}")
    
    # 初始化大小变量
    compressed_size = 0
    uncompressed_size = 0
    
    # 方法1: 尝试从LayersData获取（部分skopeo版本）
    layers_data = result.get('LayersData', [])
    if layers_data:
        logger.info("从LayersData字段计算大小")
        for layer in layers_data:
            layer_size = layer.get('Size', 0)
            logger.debug(f"图层大小: {layer_size}")
            compressed_size += layer_size
            
            # 计算未压缩大小
            if 'UncompressedSize' in layer:
                uncompressed_size += layer.get('UncompressedSize', 0)
    
    # 方法2: 如果没有LayersData，尝试从digest获取大小
    elif 'Layers' in result:
        logger.info("从manifest和config计算大小")
        # 使用同样的skopeo命令，但添加--raw参数获取原始manifest
        image = result.get('Name', '').replace('docker://', '')
        if image:
            try:
                # 获取manifest
                cmd = ['skopeo', 'inspect', '--raw', f'docker://{image}']
                logger.debug(f"执行命令获取原始manifest: {' '.join(cmd)}")
                
                manifest_process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True
                )
                
                if manifest_process.returncode == 0:
                    manifest = json.loads(manifest_process.stdout)
                    
                    # 从manifest中获取层大小
                    if 'layers' in manifest:
                        for layer in manifest.get('layers', []):
                            if 'size' in layer:
                                size = layer.get('size', 0)
                                logger.debug(f"从manifest获取图层大小: {size}")
                                compressed_size += size
                    
                    # 如果是v1格式的manifest
                    elif 'fsLayers' in manifest and 'history' in manifest:
                        logger.debug("检测到v1格式的manifest")
                        # 这种格式需要进一步处理
                        # 由于v1格式不直接包含大小信息，可能需要其他方法
            except Exception as e:
                logger.error(f"获取manifest时出错: {str(e)}")
    
    # 方法3: 如果存在Size字段（某些skopeo版本）
    if compressed_size == 0 and 'Size' in result:
        logger.info("从顶层Size字段获取大小")
        compressed_size = result.get('Size', 0)
    
    # 如果未压缩大小仍为0，但我们有压缩大小，则估算未压缩大小
    if uncompressed_size == 0 and compressed_size > 0:
        logger.info("估算未压缩大小（使用1.7倍系数）")
        uncompressed_size = compressed_size * 1.7
    
    logger.info(f"计算结果 - 压缩大小: {compressed_size} 字节, 未压缩/估算大小: {uncompressed_size} 字节")
    return compressed_size, uncompressed_size

@app.route('/image-size')
@require_api_key
@cache.cached(timeout=None, make_cache_key=make_cache_key)
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
    
    # 生成缓存键用于日志
    cache_key = make_cache_key()
    # 检查是否已缓存，方法是尝试获取值并检查是否存在
    cached_value = cache.get(cache_key)
    cached = cached_value is not None
    logger.info(f"缓存状态: {'命中' if cached else '未命中'}")
    
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
        
        # 添加缓存响应头
        resp = jsonify(response)
        # 正确的缓存状态检查
        is_cached = cache.get(make_cache_key()) is not None
        resp.headers['X-Cache-Status'] = 'HIT' if is_cached else 'MISS'
        resp.headers['X-Cache-TTL'] = str(cache_config["CACHE_DEFAULT_TIMEOUT"])
        resp.headers['X-Cache-Type'] = cache_config["CACHE_TYPE"]
        return resp
        
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
@require_api_key
@cache.cached(timeout=None, make_cache_key=make_cache_key)
def image_info():
    # 获取请求参数
    image = request.args.get('image', '')
    if not image:
        return jsonify({
            'status': 'error',
            'message': '请提供镜像名称，例如：/image-info?image=nginx:latest'
        }), 400
    
    logger.info(f"开始处理镜像请求: {image}")
    
    # 生成缓存键用于日志
    cache_key = make_cache_key()
    # 检查是否已缓存，方法是尝试获取值并检查是否存在
    cached_value = cache.get(cache_key)
    cached = cached_value is not None
    logger.info(f"缓存状态: {'命中' if cached else '未命中'}")
    
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
        
        # 添加缓存响应头
        resp = jsonify(response)
        # 正确的缓存状态检查
        is_cached = cache.get(make_cache_key()) is not None
        resp.headers['X-Cache-Status'] = 'HIT' if is_cached else 'MISS'
        resp.headers['X-Cache-TTL'] = str(cache_config["CACHE_DEFAULT_TIMEOUT"])
        resp.headers['X-Cache-Type'] = cache_config["CACHE_TYPE"]
        return resp
        
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

@app.route('/cache-info')
@require_api_key
def cache_info():
    """获取缓存状态信息"""
    # 尝试获取缓存状态
    status = "active"
    stats = {}
    
    try:
        if hasattr(cache, 'get_stats'):
            stats = cache.get_stats()
        
        return jsonify({
            "status": "success",
            "cache_type": cache_config["CACHE_TYPE"],
            "cache_timeout": cache_config["CACHE_DEFAULT_TIMEOUT"],
            "cache_stats": stats,
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"获取缓存信息失败: {str(e)}",
        }), 500

@app.route('/cache-clear')
@require_api_key
def cache_clear():
    """清除缓存"""
    try:
        cache.clear()
        logger.info("已清除所有缓存")
        return jsonify({
            "status": "success",
            "message": "缓存已清除"
        })
    except Exception as e:
        logger.error(f"清除缓存失败: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"清除缓存失败: {str(e)}"
        }), 500

if __name__ == '__main__':
    # 打印启动信息
    logger.info("Docker镜像大小查询服务启动中...")
    
    app.run(host='0.0.0.0', port=8000) 