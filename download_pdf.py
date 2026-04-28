"""下载 CSDN 文章为 PDF"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

def download_pdf():
    url = 'https://blog.csdn.net/shizheng_Li/article/details/146338734'
    output_path = 'e:/GitCode/NewsQoder/脑科学前沿进展报告.pdf'
    
    print('正在启动浏览器...')
    
    # 配置 Chrome 选项
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # 无头模式
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # 设置打印参数
    chrome_options.add_argument('--print-to-pdf=' + output_path.replace('/', '\\'))
    chrome_options.add_argument('--run-all-compositor-stages-before-draw')
    
    # 启动浏览器
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    try:
        print('正在加载页面...')
        driver.get(url)
        time.sleep(5)  # 等待页面加载
        
        # 使用 Chrome DevTools Protocol 生成 PDF
        result = driver.execute_cdp_cmd('Page.printToPDF', {
            'printBackground': True,
            'preferCSSPageSize': True,
            'paperWidth': 8.27,  # A4 宽度（英寸）
            'paperHeight': 11.69,  # A4 高度（英寸）
        })
        
        # 保存 PDF
        import base64
        with open(output_path, 'wb') as f:
            f.write(base64.b64decode(result['data']))
        
        print(f'PDF 已生成: {output_path}')
        
    finally:
        driver.quit()

if __name__ == '__main__':
    download_pdf()
