# olrgu

局域网文件分享工具。选个文件夹，输个端口，局域网内任意设备用浏览器访问即可。  
作者：KS_CM  
版本：1.0.0

## 功能

- 选择文件夹或单个文件共享
- 自定义端口（四位数字）
- 可选密码保护（六位以内数字）
- 在线预览：图片 / 文本 / PDF
- 端口占用检测，冲突时提示
- 最多同时运行 2 个服务实例

## 安装

下载 `olrgu-setup.exe` 运行即可，会自动下载主程序并创建桌面快捷方式。

安装路径：`%LOCALAPPDATA%\olrgu\`

## 从源码运行

```bash
pip install -r requirements.txt
python olrgu.py
```

## 使用

1. 选择要共享的文件夹或文件
2. 设置端口（默认 8000）
3. 可选设置密码
4. 点击"启动服务"
5. 局域网设备浏览器访问显示的地址

## 支持预览的格式

| 类型 | 格式 |
|------|------|
| 图片 | jpg, jpeg, png, gif, webp |
| 文本 | txt, md, json, xml, html, css, js, py |
| 文档 | pdf |

## 技术栈

- Python 3.13 + CustomTkinter
- Python HTTPServer
- PyInstaller 打包

## 注意

- 防火墙需放行对应端口
- 密码保护仅为基础访问控制，不适用于高安全场景
