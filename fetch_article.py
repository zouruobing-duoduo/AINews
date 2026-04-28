"""获取 CSDN 文章并保存为 HTML"""
import requests
from bs4 import BeautifulSoup

url = 'https://blog.csdn.net/shizheng_Li/article/details/146338734'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

resp = requests.get(url, headers=headers, timeout=30)
print(f'状态码: {resp.status_code}')

if resp.status_code == 200:
    soup = BeautifulSoup(resp.text, 'html.parser')
    title = soup.find('h1', class_='title-article')
    content = soup.find('div', id='content_views')
    
    if title and content:
        title_text = title.get_text(strip=True)
        print(f'标题: {title_text}')
        print(f'内容长度: {len(content.get_text())} 字符')
        
        # 保存为 HTML
        html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{title_text}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.8; }}
h1 {{ color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
img {{ max-width: 100%; }}
code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
pre {{ background: #f4f4f4; padding: 15px; overflow-x: auto; border-radius: 5px; }}
</style>
</head>
<body>
<h1>{title_text}</h1>
{str(content)}
</body>
</html>'''
        with open('e:/GitCode/NewsQoder/article_temp.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print('HTML 已保存到 article_temp.html')
    else:
        print('未找到文章内容')
        if not title:
            print('- 标题未找到')
        if not content:
            print('- 内容未找到')
else:
    print(f'请求失败: {resp.status_code}')
