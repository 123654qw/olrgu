#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
olrgu - 局域网文件分享工具
简洁、高效的本地文件服务器，支持文件预览和密码保护
"""

import os
import sys
import socket
import threading
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import mimetypes
import urllib.parse
import json

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter.font as tkFont

# 全局变量：跟踪活动服务器数量（限制为2个）
_active_servers = 0
_MAX_SERVERS = 2


class FileServer(HTTPServer):
    """自定义HTTP服务器，支持密码保护和文件预览"""

    def __init__(self, server_address, handler_class, share_path, password=None):
        super().__init__(server_address, handler_class)
        self.share_path = share_path
        self.is_file = os.path.isfile(share_path)  # 是否为单个文件
        self.password = password
        self.authenticated = set()  # 存储已认证的客户端IP


class FileHandler(SimpleHTTPRequestHandler):
    """自定义文件处理程序"""

    def do_GET(self):
        """处理GET请求"""
        server = self.server

        # 检查认证
        client_ip = self.client_address[0]
        if server.password and client_ip not in server.authenticated:
            self.send_auth_required()
            return

        # 解析路径
        parsed_path = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed_path.path)

        if path == '/':
            self.serve_index()
        elif path == '/auth':
            self.handle_auth(parsed_path.query)
        else:
            self.serve_file(path[1:])  # 移除开头的 '/'

    def do_POST(self):
        """处理POST请求（用于密码验证）"""
        server = self.server
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(post_data)
            if data.get('password') == server.password:
                client_ip = self.client_address[0]
                server.authenticated.add(client_ip)
                self.send_json_response({'success': True})
            else:
                self.send_json_response({'success': False, 'error': '密码错误'})
        except:
            self.send_json_response({'success': False, 'error': '请求格式错误'})

    def serve_index(self):
        """提供文件列表页面"""
        server = self.server
        share_path = Path(server.share_path)

        html = self.generate_html(share_path)
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def generate_html(self, share_path):
        """生成文件列表HTML页面"""
        files = []
        server = self.server

        # 检查是单个文件还是文件夹
        if server.is_file:
            # 单个文件模式
            share_path_obj = Path(server.share_path)
            files.append({
                'name': share_path_obj.name,
                'is_dir': False,
                'size': share_path_obj.stat().st_size,
                'path': share_path_obj.name
            })
        else:
            # 文件夹模式
            for item in share_path.iterdir():
                if item.name.startswith('.'):
                    continue
                files.append({
                    'name': item.name,
                    'is_dir': item.is_dir(),
                    'size': item.stat().st_size if item.is_file() else 0,
                    'path': item.name
                })

            files.sort(key=lambda x: (x['is_dir'], x['name']))

        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>olrgu - 文件分享</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            padding: 20px;
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{
            font-size: 24px;
            font-weight: 400;
            margin-bottom: 30px;
            color: #fff;
            border-bottom: 1px solid #333;
            padding-bottom: 15px;
        }}
        .file-list {{
            background: #141414;
            border: 1px solid #2a2a2a;
        }}
        .file-item {{
            padding: 12px 20px;
            border-bottom: 1px solid #1f1f1f;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: background 0.15s;
        }}
        .file-item:hover {{
            background: #1a1a1a;
        }}
        .file-item:last-child {{
            border-bottom: none;
        }}
        .file-info {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
        }}
        .file-icon {{
            font-size: 20px;
            width: 30px;
            text-align: center;
        }}
        .file-name {{
            color: #e0e0e0;
            text-decoration: none;
            font-size: 14px;
        }}
        .file-name:hover {{
            color: #4a9eff;
        }}
        .file-size {{
            color: #666;
            font-size: 12px;
            margin-left: 10px;
        }}
        .file-actions {{
            display: flex;
            gap: 10px;
        }}
        .btn {{
            padding: 6px 14px;
            font-size: 12px;
            border: 1px solid #333;
            background: transparent;
            color: #e0e0e0;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.15s;
        }}
        .btn:hover {{
            background: #2a2a2a;
            border-color: #4a9eff;
            color: #4a9eff;
        }}
        .preview-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}
        .preview-content {{
            max-width: 90%;
            max-height: 90%;
            background: #141414;
            border: 1px solid #333;
            padding: 20px;
            overflow: auto;
        }}
        .preview-close {{
            position: absolute;
            top: 20px;
            right: 30px;
            color: #fff;
            font-size: 30px;
            cursor: pointer;
        }}
        .login-form {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 2000;
        }}
        .login-box {{
            background: #141414;
            border: 1px solid #333;
            padding: 40px;
            min-width: 300px;
        }}
        .login-box h2 {{
            font-size: 18px;
            font-weight: 400;
            margin-bottom: 20px;
            color: #fff;
        }}
        .login-box input {{
            width: 100%;
            padding: 10px;
            background: #0a0a0a;
            border: 1px solid #333;
            color: #e0e0e0;
            font-size: 14px;
            margin-bottom: 15px;
        }}
        .login-box button {{
            width: 100%;
            padding: 10px;
            background: #4a9eff;
            border: none;
            color: #fff;
            font-size: 14px;
            cursor: pointer;
        }}
        .login-box button:hover {{
            background: #3a8eef;
        }}
        .error-msg {{
            color: #ff4a4a;
            font-size: 12px;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <h1>olrgu 文件分享</h1>
    <div class="file-list">
"""

        if not files:
            html += '<div class="file-item" style="color:#666;">暂无共享文件</div>'
        else:
            for file in files:
                icon = '📁' if file['is_dir'] else self.get_file_icon(file['name'])
                size_str = self.format_size(file['size']) if not file['is_dir'] else ''
                preview_btn = ''
                if not file['is_dir'] and self.can_preview(file['name']):
                    preview_btn = f'<a href="#" class="btn" onclick="previewFile(\'{file["name"]}\');return false;">预览</a>'

                html += f'''
        <div class="file-item">
            <div class="file-info">
                <span class="file-icon">{icon}</span>
                <a href="/{urllib.parse.quote(file['name'])}" class="file-name">{file['name']}</a>
                <span class="file-size">{size_str}</span>
            </div>
            <div class="file-actions">
                {preview_btn}
                <a href="/{urllib.parse.quote(file['name'])}" download class="btn">下载</a>
            </div>
        </div>
'''

        html += """
    </div>

    <div id="previewModal" class="preview-modal">
        <span class="preview-close" onclick="closePreview()">&times;</span>
        <div class="preview-content" id="previewContent"></div>
    </div>

    <script>
        function previewFile(filename) {
            const modal = document.getElementById('previewModal');
            const content = document.getElementById('previewContent');
            modal.style.display = 'flex';

            const ext = filename.split('.').pop().toLowerCase();

            if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) {
                content.innerHTML = `<img src="/${filename}" style="max-width:100%;">`;
            } else if (['txt', 'md', 'json', 'xml', 'html', 'css', 'js', 'py'].includes(ext)) {
                fetch('/' + filename)
                    .then(r => r.text())
                    .then(t => {
                        content.innerHTML = `<pre style="color:#e0e0e0;white-space:pre-wrap;">${t}</pre>`;
                    });
            } else if (['pdf'].includes(ext)) {
                content.innerHTML = `<iframe src="/${filename}" style="width:100%;height:80vh;"></iframe>`;
            } else {
                content.innerHTML = '<p style="color:#666;">该文件类型不支持预览</p>';
            }
        }

        function closePreview() {
            document.getElementById('previewModal').style.display = 'none';
        }
    </script>
</body>
</html>
"""

        return html

    def can_preview(self, filename):
        """检查文件是否支持预览"""
        ext = filename.split('.')[-1].lower()
        return ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'txt', 'md', 'json', 'xml', 'html', 'css', 'js', 'py', 'pdf']

    def get_file_icon(self, filename):
        """获取文件图标"""
        ext = filename.split('.')[-1].lower()
        icons = {
            'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'webp': '🖼️',
            'pdf': '📄', 'txt': '📝', 'md': '📝', 'doc': '📄', 'docx': '📄',
            'xls': '📊', 'xlsx': '📊', 'zip': '📦', 'rar': '📦',
            'mp4': '🎬', 'mp3': '🎵', 'wav': '🎵',
            'py': '🐍', 'js': '📜', 'html': '🌐', 'css': '🎨'
        }
        return icons.get(ext, '📄')

    def format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def serve_file(self, filename):
        """提供文件下载"""
        server = self.server

        # 根据模式确定文件路径
        if server.is_file:
            # 单个文件模式：直接使用share_path
            file_path = Path(server.share_path)
        else:
            # 文件夹模式：拼接路径
            share_path = Path(server.share_path)
            file_path = share_path / filename

            # 安全检查：防止目录遍历攻击
            try:
                file_path_resolved = file_path.resolve()
                share_path_resolved = share_path.resolve()
                if not str(file_path_resolved).startswith(str(share_path_resolved)):
                    self.send_error(403, "禁止访问")
                    return
            except:
                self.send_error(404, "文件不存在")
                return

        # 检查文件是否存在
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, '文件不存在')
            return

        try:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = 'application/octet-stream'

            self.send_response(200)
            self.send_header('Content-type', mime_type)
            self.send_header('Content-Disposition', f'inline; filename="{urllib.parse.quote(file_path.name)}"')
            self.send_header('Content-Length', str(file_path.stat().st_size))
            self.end_headers()

            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())

        except Exception as e:
            self.send_error(500, f'服务器错误: {str(e)}')

    def send_auth_required(self):
        """发送认证要求"""
        html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>olrgu - 需要密码</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .login-box {
            background: #141414;
            border: 1px solid #333;
            padding: 40px;
            min-width: 320px;
        }
        .login-box h2 {
            font-size: 18px;
            font-weight: 400;
            margin-bottom: 25px;
            color: #fff;
        }
        .login-box input {
            width: 100%;
            padding: 12px;
            background: #0a0a0a;
            border: 1px solid #333;
            color: #e0e0e0;
            font-size: 14px;
            margin-bottom: 15px;
        }
        .login-box button {
            width: 100%;
            padding: 12px;
            background: #4a9eff;
            border: none;
            color: #fff;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.15s;
        }
        .login-box button:hover {
            background: #3a8eef;
        }
        .error-msg {
            color: #ff4a4a;
            font-size: 12px;
            margin-bottom: 10px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>olrgu 文件分享</h2>
        <div class="error-msg" id="errorMsg">密码错误</div>
        <input type="password" id="password" placeholder="请输入访问密码" autofocus>
        <button onclick="login()">访问</button>
    </div>

    <script>
        function login() {
            const pwd = document.getElementById('password').value;
            fetch('/api/auth', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({password: pwd})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    document.getElementById('errorMsg').style.display = 'block';
                    document.getElementById('password').value = '';
                }
            });
        }

        document.getElementById('password').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') login();
        });
    </script>
</body>
</html>
"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def send_json_response(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def log_message(self, format, *args):
        """重写日志方法，使用自定义格式"""
        pass  # 禁用默认日志


class OlrguApp:
    """olrgu 主应用程序"""

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("olrgu")
        self.root.geometry("650x500")
        self.root.configure(bg="#0a0a0a")

        # 设置窗口图标（必须在创建窗口后设置）
        self.root.after(100, self.set_icon)

        # 设置主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.share_path = None
        self.server = None
        self.server_thread = None
        self.is_running = False

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        # 主容器
        main_frame = ctk.CTkFrame(self.root, fg_color="#0a0a0a", border_width=0)
        main_frame.pack(fill="both", expand=True, padx=30, pady=30)

        # 标题
        title_label = ctk.CTkLabel(
            main_frame,
            text="olrgu",
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="normal"),
            text_color="#ffffff"
        )
        title_label.pack(pady=(0, 10))

        # 副标题
        subtitle_label = ctk.CTkLabel(
            main_frame,
            text="局域网文件分享工具",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#666666"
        )
        subtitle_label.pack(pady=(0, 30))

        # 文件选择区域
        file_frame = ctk.CTkFrame(main_frame, fg_color="#141414", border_width=1, border_color="#2a2a2a")
        file_frame.pack(fill="x", pady=(0, 15))

        file_label = ctk.CTkLabel(
            file_frame,
            text="共享内容",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#999999",
            anchor="w"
        )
        file_label.pack(fill="x", padx=15, pady=(10, 5))

        # 选择按钮区域
        select_btn_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
        select_btn_frame.pack(fill="x", padx=15, pady=(0, 5))

        self.select_dir_btn = ctk.CTkButton(
            select_btn_frame,
            text="选择文件夹",
            command=self.select_directory,
            height=28,
            fg_color="#2a2a2a",
            hover_color="#3a3a3a",
            text_color="#e0e0e0",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            corner_radius=0,
            width=100
        )
        self.select_dir_btn.pack(side="left", padx=(0, 10))

        self.select_file_btn = ctk.CTkButton(
            select_btn_frame,
            text="选择文件",
            command=self.select_file,
            height=28,
            fg_color="#2a2a2a",
            hover_color="#3a3a3a",
            text_color="#e0e0e0",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            corner_radius=0,
            width=100
        )
        self.select_file_btn.pack(side="left")

        # 显示选择的路径
        self.file_path_var = ctk.StringVar(value="未选择")
        self.file_path_label = ctk.CTkLabel(
            file_frame,
            textvariable=self.file_path_var,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#4a9eff",
            anchor="w",
            height=30
        )
        self.file_path_label.pack(fill="x", padx=15, pady=(5, 10))

        # 设置区域
        settings_frame = ctk.CTkFrame(main_frame, fg_color="#141414", border_width=1, border_color="#2a2a2a")
        settings_frame.pack(fill="x", pady=(0, 15))

        # 端口设置
        port_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        port_frame.pack(fill="x", padx=15, pady=10)

        port_label = ctk.CTkLabel(
            port_frame,
            text="端口号",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#999999",
            width=80,
            anchor="w"
        )
        port_label.pack(side="left")

        self.port_entry = ctk.CTkEntry(
            port_frame,
            placeholder_text="四位端口号 (如: 8000)",
            width=120,
            height=30,
            border_width=1,
            border_color="#333333",
            fg_color="#0a0a0a",
            text_color="#e0e0e0",
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.port_entry.pack(side="left", padx=(0, 10))
        self.port_entry.insert(0, "8000")

        # 密码设置
        pwd_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        pwd_frame.pack(fill="x", padx=15, pady=(0, 10))

        pwd_label = ctk.CTkLabel(
            pwd_frame,
            text="访问密码",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#999999",
            width=80,
            anchor="w"
        )
        pwd_label.pack(side="left")

        self.pwd_entry = ctk.CTkEntry(
            pwd_frame,
            placeholder_text="可选，六位以内",
            width=120,
            height=30,
            border_width=1,
            border_color="#333333",
            fg_color="#0a0a0a",
            text_color="#e0e0e0",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            show="●"
        )
        self.pwd_entry.pack(side="left")

        # 按钮区域
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 15))

        self.start_btn = ctk.CTkButton(
            button_frame,
            text="启动服务",
            command=self.start_server,
            height=35,
            fg_color="#4a9eff",
            hover_color="#3a8eef",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            corner_radius=0
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="停止服务",
            command=self.stop_server,
            height=35,
            fg_color="#333333",
            hover_color="#444444",
            text_color="#e0e0e0",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            corner_radius=0,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(0, 10))

        self.browser_btn = ctk.CTkButton(
            button_frame,
            text="打开浏览器",
            command=self.open_browser,
            height=35,
            fg_color="#333333",
            hover_color="#444444",
            text_color="#e0e0e0",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            corner_radius=0,
            state="disabled"
        )
        self.browser_btn.pack(side="left")

        # 状态显示
        self.status_text = ctk.CTkTextbox(
            main_frame,
            height=100,
            fg_color="#141414",
            border_width=1,
            border_color="#2a2a2a",
            text_color="#999999",
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.status_text.pack(fill="x")
        self.status_text.insert("1.0", "就绪\n")
        self.status_text.configure(state="disabled")

    def select_directory(self):
        """选择共享目录"""
        directory = filedialog.askdirectory(title="选择共享目录")
        if directory:
            self.share_path = directory
            self.file_path_var.set(f"[文件夹] {directory}")

    def select_file(self):
        """选择单个文件"""
        file = filedialog.askopenfilename(title="选择文件")
        if file:
            self.share_path = file
            self.file_path_var.set(f"[文件] {file}")

    def get_local_ip(self):
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def check_port(self, port):
        """检查端口是否被占用"""
        try:
            # 尝试绑定端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', port))
            sock.close()
            return True  # 端口可用
        except OSError:
            return False  # 端口已被占用

    def set_icon(self):
        """设置窗口图标（兼容CustomTkinter）"""
        try:
            # 获取图标文件路径
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
                png_path = os.path.join(sys._MEIPASS, 'icon.png')
            else:
                icon_path = 'icon.ico'
                png_path = 'icon.png'

            # 方法1: 使用iconbitmap（Windows）
            try:
                self.root.iconbitmap(icon_path)
            except:
                pass

            # 方法2: 使用iconphoto（更可靠，支持PNG）
            try:
                import tkinter as tk
                # 读取PNG并转换为PhotoImage
                img = tk.PhotoImage(file=png_path)
                self.root.iconphoto(True, img)
                # 保持引用，防止被垃圾回收
                self._icon_img = img
            except Exception as e:
                print(f"iconphoto失败: {e}")
                pass

        except Exception as e:
            print(f"设置图标失败: {e}")
            pass

    def start_server(self):
        """启动HTTP服务器"""
        global _active_servers

        if self.is_running:
            return

        # 检查是否超过最大服务器数量
        if _active_servers >= _MAX_SERVERS:
            messagebox.showerror("提示", "你需要订阅才可以运行更多的olrgu")
            return

        # 验证端口
        port_str = self.port_entry.get().strip()
        if not port_str.isdigit() or len(port_str) != 4:
            messagebox.showerror("错误", "请输入四位端口号")
            return

        port = int(port_str)

        # 检查端口是否被占用
        if not self.check_port(port):
            messagebox.showerror("错误", f"端口 {port} 已被占用，请选择其他端口")
            return

        # 验证路径
        if not self.share_path or not os.path.exists(self.share_path):
            messagebox.showerror("错误", "请选择文件或目录")
            return

        # 验证密码
        password = self.pwd_entry.get().strip()
        if password and (len(password) > 6 or not password.isdigit()):
            messagebox.showerror("错误", "密码必须是六位以内的数字")
            return

        # 启动服务器
        try:
            self.server = FileServer(
                ("0.0.0.0", port),
                FileHandler,
                self.share_path,
                password if password else None
            )

            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()

            self.is_running = True

            # 增加活动服务器计数
            _active_servers += 1

            # 更新UI
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.browser_btn.configure(state="normal")

            # 显示访问信息
            local_ip = self.get_local_ip()
            url = f"http://{local_ip}:{port}"

            self.update_status(f"服务已启动\n")
            self.update_status(f"本地访问: http://localhost:{port}\n")
            self.update_status(f"局域网访问: {url}\n")
            self.update_status(f"共享目录: {self.share_path}\n")

            if password:
                self.update_status(f"访问密码: {password}\n")

        except Exception as e:
            messagebox.showerror("错误", f"启动服务器失败: {str(e)}")

    def stop_server(self):
        """停止HTTP服务器"""
        global _active_servers

        if not self.is_running:
            return

        try:
            self.server.shutdown()
            self.server.server_close()
            self.is_running = False

            # 减少活动服务器计数
            _active_servers -= 1

            # 更新UI
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.browser_btn.configure(state="disabled")

            self.update_status("服务已停止\n")

        except Exception as e:
            messagebox.showerror("错误", f"停止服务器失败: {str(e)}")

    def open_browser(self):
        """在浏览器中打开"""
        if not self.is_running:
            return

        port = self.port_entry.get().strip()
        webbrowser.open(f"http://localhost:{port}")

    def update_status(self, message):
        """更新状态显示"""
        self.status_text.configure(state="normal")
        self.status_text.insert("end", message)
        self.status_text.see("end")
        self.status_text.configure(state="disabled")

    def run(self):
        """运行应用程序"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        """关闭窗口时的处理"""
        if self.is_running:
            self.stop_server()
        self.root.destroy()


if __name__ == "__main__":
    app = OlrguApp()
    app.run()
