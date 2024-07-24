import os
from notion_client import Client
from markdownify import markdownify as md
import requests
from datetime import datetime

# 初始化 Notion 客户端
notion = Client(auth="API Key")

# 获取数据库中的条目
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

# 获取页面内容
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
# 下载图片并返回相对路径
def download_image(url, image_name, post_dir):
    response = requests.get(url)
    image_path = os.path.join(post_dir, image_name)
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    with open(image_path, 'wb') as file:
        file.write(response.content)
    return f"{post_dir}/{image_name}"

# 将页面内容转换为 Markdown
def convert_to_markdown(title, date, tags, blocks, post_dir):
    # 添加元数据
    markdown = f"---\ntitle: {title}\ndate: {date}\ntags: {tags}\n---\n\n"
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
        # 可以根据需要添加更多块类型的处理
    return markdown


# 保存为 Markdown 文件
def save_markdown_file(file_name, content):
    with open(f'./source/_posts/{file_name}.md', 'w', encoding='utf-8') as file:
        file.write(content)

# 更新 Notion 页面状态
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


# 主函数
def main():
    database_id = "Database ID"
    filter_status = "待發佈"
    new_status = "已發佈"
    items = fetch_database_items(database_id, filter_status)
    
    for item in items:
        page_id = item["id"]
        # 提取标题、日期和标签
        title = item["properties"]["title"]["title"][0]["text"]["content"]
        date = item["properties"]["date"]["date"]["start"] if item["properties"]["date"]["date"] else datetime.now().isoformat()
        tags = ', '.join(tag["name"] for tag in item["properties"]["tags"]["multi_select"]) if item["properties"]["tags"]["multi_select"] else "null"
        
        # 创建用于存放图片的目录
        post_dir = f"./source/_posts/{title.replace(' ', '_')}"
        
        blocks = fetch_page_content(page_id)
        markdown_content = convert_to_markdown(title, date, tags, blocks, post_dir)
        save_markdown_file(title, markdown_content)
        print(f"Saved: {title}")
        
        # 更新状态为 "已發佈"
        update_page_status(page_id, new_status)
        print(f"Updated status for {title} to {new_status}")

if __name__ == "__main__":
    main()
