import os
from notion_client import Client
from markdownify import markdownify as md
import requests
from datetime import datetime

# Initialize Notion client
notion = Client(auth="API KEY")

# Fetch database items
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

# Fetch page content
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

# Download image and return relative path
def download_image(url, image_name, image_dir):
    response = requests.get(url)
    image_path = os.path.join(image_dir, image_name)
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    with open(image_path, 'wb') as file:
        file.write(response.content)
    return image_path

# Convert page content to Markdown
def convert_to_markdown(title, date, tags, categories, index_img_path, blocks, post_dir):
    # Add metadata
    markdown = f"---\ntitle: {title}\ndate: {date}\ntags: [{tags}]\ncategories: {categories}\nindex_img: {index_img_path}\nbanner_img: {index_img_path}\n---\n\n"
    for block in blocks:
        block_type = block["type"]
        if block_type == "paragraph":
            if block[block_type]["rich_text"]:
                for text in block[block_type]["rich_text"]:
                    if "href" in text["text"]:
                        markdown += f"[{text['text']['content']}]({text['text']['href']})"
                    else:
                        markdown += md(text["text"]["content"])
                markdown += "\n\n"
        elif block_type == "heading_2":
            if block[block_type]["rich_text"]:
                markdown += "## " + md(block[block_type]["rich_text"][0]["text"]["content"]) + "\n\n"
        elif block_type == "heading_3":
            if block[block_type]["rich_text"]:
                markdown += "### " + md(block[block_type]["rich_text"][0]["text"]["content"]) + "\n\n"
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
            markdown += f"![Image]({os.path.basename(image_path)})\n\n"
        # Add more block type handling as needed
    return markdown

# Save as Markdown file
def save_markdown_file(file_name, content):
    with open(f'./source/_posts/{file_name}.md', 'w', encoding='utf-8') as file:
        file.write(content)

# Update Notion page status
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

# Main function
def main():
    database_id = "Database ID"
    filter_status = "待發佈"
    new_status = "已發佈"
    items = fetch_database_items(database_id, filter_status)
    
    for item in items:
        page_id = item["id"]
        # Extract title, date, tags, categories, and index image
        title = item["properties"]["title"]["title"][0]["text"]["content"]
        date = item["properties"]["date"]["date"]["start"] if item["properties"]["date"]["date"] else datetime.now().isoformat()
        tags = ', '.join(tag["name"] for tag in item["properties"]["tags"]["multi_select"]) if item["properties"]["tags"]["multi_select"] else "null"
        categories = ', '.join(cat["name"] for cat in item["properties"]["categories"]["multi_select"]) if item["properties"]["categories"]["multi_select"] else "null"
        index_img_url = item["properties"]["index_img"]["files"][0]["file"]["url"] if item["properties"]["index_img"]["files"] else None
        
        # Directory for index image
        index_img_dir = "./themes/fluid/source/img"
        os.makedirs(index_img_dir, exist_ok=True)
        
        # Download index image
        index_img_path = None
        if index_img_url:
            index_img_name = f"{title.replace(' ', '_')}_index.jpg"
            index_img_path = download_image(index_img_url, index_img_name, index_img_dir)
            index_img_path = f"/img/{index_img_name}"  # Path used in the markdown metadata

        # Directory for other post images
        post_dir = f"./source/_posts/{title.replace(' ', '_')}"
        os.makedirs(post_dir, exist_ok=True)

        blocks = fetch_page_content(page_id)
        markdown_content = convert_to_markdown(title, date, tags, categories, index_img_path, blocks, post_dir)
        save_markdown_file(title, markdown_content)
        print(f"Saved: {title}")
        
        # Update status to "已發佈"
        update_page_status(page_id, new_status)
        print(f"Updated status for {title} to {new_status}")

if __name__ == "__main__":
    main()

