import os
from notion_client import Client
from markdownify import markdownify as md
import requests
from datetime import datetime

# 初始化 Notion 客戶端
notion = Client(auth="你的API Key")

# 獲取數據庫中的條目
def fetch_database_items(database_id, filter_status):
    response = notion.databases.query(
        **{
            "database_id": database_id,
            "filter": {
                "property": "status",
                "select": {
                    "equals": filter_status
                }
            }
        }
    )
    return response.get('results', [])

# 獲取頁面內容
def fetch_page_content(page_id):
    blocks = []
    cursor = None
    while True:
        response = notion.blocks.children.list(block_id=page_id, start_cursor=cursor)
        blocks.extend(response.get('results', []))
        cursor = response.get('next_cursor')
        if not cursor:
            break
    return blocks

# 下載圖片並返回相對路徑
def download_image(url, image_name, post_dir):
    response = requests.get(url)
    image_path = os.path.join(post_dir, image_name)
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    with open(image_path, 'wb') as file:
        file.write(response.content)
    return f"{post_dir}/{image_name}"

# 將頁面內容轉換為 Markdown
def convert_to_markdown(title, date, tags, categories, index_img, blocks, post_dir):
    # 添加元數據
    markdown = f"---\ntitle: {title}\ndate: {date}\ntags: {tags}\ncategories: {categories}\nindex_img: {index_img}\n---\n\n"
    for block in blocks:
        block_type = block["type"]
        if block_type == "paragraph":
            if block[block_type]["rich_text"]:
                markdown += md(block[block_type]["rich_text"][0]["text"]["content"]) + "\n\n"
        elif block_type == "heading_2":
            if block[block_type]["rich_text"]:
                markdown += "## " + md(block[block_type]["rich_text"][0]["text"]["content"]) + "\n\n"
        elif block_type == "bulleted_list_item":
            if block[block_type]["rich_text"]:
                markdown += "- " + md(block[block_type]["rich_text"][0]["text"]["content"]) + "\n\n"
        elif block_type == "image":
            if "external" in block[block_type]:
                image_url = block[block_type]["external"]["url"]
            elif "file" in block[block_type]:
                image_url = block[block_type]["file"]["url"]
            else:
                continue
            image_name = block["id"] + ".jpg"
            image_path = download_image(image_url, image_name, post_dir)
            markdown += f"![Image]({image_name})\n\n"
        # 可以根據需要添加更多塊類型的處理
    return markdown

# 保存為 Markdown 文件
def save_markdown_file(file_name, content):
    with open(f'./source/_posts/{file_name}.md', 'w', encoding='utf-8') as file:
        file.write(content)

# 更新 Notion 頁面狀態
def update_page_status(page_id, new_status):
    notion.pages.update(
        page_id=page_id,
        properties={
            "status": {
                "select": {
                    "name": new_status
                }
            }
        }
    )

# 主函數
def main():
    database_id = "你的數據庫ID"
    filter_status = "待發佈"
    new_status = "已發佈"
    items = fetch_database_items(database_id, filter_status)
    
    for item in items:
        page_id = item["id"]
        # 提取標題、日期、標籤、分類和索引圖片
        title = item["properties"]["title"]["title"][0]["text"]["content"]
        date = item["properties"]["date"]["date"]["start"] if item["properties"]["date"]["date"] else datetime.now().isoformat()
        tags = ', '.join(tag["name"] for tag in item["properties"]["tags"]["multi_select"]) if item["properties"]["tags"]["multi_select"] else "null"
        categories = ', '.join(cat["name"] for cat in item["properties"]["categories"]["multi_select"]) if item["properties"]["categories"]["multi_select"] else "null"
        index_img = item["properties"]["index_img"]["files"][0]["name"] if item["properties"]["index_img"]["files"] else "null"
        
        # 創建用於存放圖片的目錄
        post_dir = f"./source/_posts/{title.replace(' ', '_')}"
        
        blocks = fetch_page_content(page_id)
        markdown_content = convert_to_markdown(title, date, tags, categories, index_img, blocks, post_dir)
        save_markdown_file(title, markdown_content)
        print(f"Saved: {title}")
        
        # 更新狀態為 "已發佈"
        update_page_status(page_id, new_status)
        print(f"Updated status for {title} to {new_status}")

if __name__ == "__main__":
    main()
