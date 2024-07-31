import os
import openai
from notion_client import Client
from PIL import Image
import requests
from datetime import datetime

# 假设 default_image_path 是你默认图片的相对路径
default_image_path = "img/default.webp"

# Initialize Notion client
notion = Client(auth="notion-api-key")
openai.api_key = 'openai-api-key'


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
    # Check for child blocks in each block and fetch them
    for block in blocks:
        if block["has_children"]:
            child_blocks = fetch_page_content(block["id"])
            block["children"] = child_blocks
    return blocks


# Download image and convert to WebP
# 下载图像并转换为WebP格式
def download_image_as_webp(url, image_name, image_dir):
    try:
        print(f"Downloading image from URL: {url}")
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"Failed to download image, status code: {response.status_code}")
            return None
        
        # 确保目标目录存在
        os.makedirs(image_dir, exist_ok=True)
        image_path = os.path.join(image_dir, image_name)
        
        # 保存下载的图像
        with open(image_path, 'wb') as file:
            file.write(response.content)
        
        print(f"Image saved to {image_path}, converting to WebP format.")
        
        try:
            # 转换为WebP格式
            with Image.open(image_path) as img:
                webp_image_path = os.path.splitext(image_path)[0] + '.webp'
                img.save(webp_image_path, 'WEBP')
            
            print(f"Image converted to WebP format at {webp_image_path}")
            return webp_image_path
        
        except Exception as e:
            print(f"An error occurred during image conversion: {e}")
            return None
    
    except Exception as e:
        print(f"An error occurred while downloading or converting the image: {e}")
        return None



# Generate SEO-friendly URL name using OpenAI
def generate_seo_url_name(title, tags):
    # Translate title and tags to English
    translation_prompt = f"Translate the following Chinese text to English: Title: '{title}', Tags: '{tags}'"
    translation_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a translation assistant."},
            {"role": "user", "content": translation_prompt}
        ]
    )
    translation = translation_response['choices'][0]['message']['content'].strip()

    # Generate SEO-friendly URL name
    seo_prompt = f"Generate a SEO-friendly URL name based on the English translation: {translation}"
    seo_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an assistant that generates SEO-friendly URL slugs."},
            {"role": "user", "content": seo_prompt}
        ]
    )
    slug = seo_response['choices'][0]['message']['content'].strip()
    slug = slug.replace(" ", "-").lower()
    return slug


# Extract rich text with possible links and code
def extract_rich_text_with_links_and_code(rich_texts):
    text = ""
    for rich_text in rich_texts:
        if rich_text["type"] == "text":
            content_data = rich_text.get("text", {})
            content = content_data.get("content", "")
            
            link_data = content_data.get("link", None)
            if link_data and isinstance(link_data, dict):
                link_url = link_data.get("url")
                if link_url:
                    text += f"[{content}]({link_url})"
                else:
                    text += content
            elif rich_text.get("annotations", {}).get("code", False):
                text += f"`{content}`"
            else:
                text += content
        elif rich_text["type"] == "mention":
            mention = rich_text["mention"]
            if mention["type"] == "page":
                page_id = mention["page"]["id"]
                text += f"[Mention: {page_id}]"
            elif mention["type"] == "user":
                user_name = mention["user"].get("name", "Unknown User")
                text += f"@{user_name}"
        elif rich_text["type"] == "equation":
            equation = rich_text["equation"]["expression"]
            text += f"${equation}$"
    return text



# Convert page content to Markdown
def convert_to_markdown(title, date, tags, categories, index_img_path, blocks, post_dir, url_name,is_child):
    markdown=''
    if not is_child:
        markdown = f"---\ntitle: {title}\ndate: {date}\ntags: [{tags}]\ncategories: {categories}\nindex_img: {index_img_path}\nbanner_img: {index_img_path}\nabbrlink: {url_name}\n---\n\n"
    for block in blocks:
        block_type = block["type"]
        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
            if block[block_type]["rich_text"]:
                text_content = extract_rich_text_with_links_and_code(block[block_type]["rich_text"])
                if block_type == "heading_1":
                    markdown += f"# {text_content}\n\n"
                elif block_type == "heading_2":
                    markdown += f"## {text_content}\n\n"
                elif block_type == "heading_3":
                    markdown += f"### {text_content}\n\n"
                elif block_type == "bulleted_list_item":
                    markdown += f"- {text_content}\n\n"
                elif block_type == "numbered_list_item":
                    markdown += f"1. {text_content}\n\n"
                else:
                    markdown += f"{text_content}\n\n"
        elif block_type == "code":
            code_content = "".join(rt["text"]["content"] for rt in block[block_type]["rich_text"])
            markdown += f"```\n{code_content}\n```\n\n"
        elif block_type == "image":
            if "external" in block[block_type]:
                image_url = block[block_type]["external"]["url"]
            elif "file" in block[block_type]:
                image_url = block[block_type]["file"]["url"]
            else:
                continue
            image_name = block["id"] + ".webp"
            image_path = download_image_as_webp(image_url, image_name, post_dir)
            if image_path:  # 确保 image_path 不是 None
                markdown += f"![Image]({os.path.basename(image_path)})\n\n"
            else:
                print(f"Warning: Image for block {block['id']} could not be downloaded or converted.")
        elif block_type == "embed":
            if "url" in block[block_type]:
                embed_url = block[block_type]["url"]
                markdown += f"[Embedded Content]({embed_url})\n\n"
        # Process child blocks if they exist
        if block.get("children"):
            child_markdown = convert_to_markdown(title, date, tags, categories, index_img_path, block["children"], post_dir, url_name,1)
            markdown += child_markdown
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
    database_id = "database-id"
    filter_status = "待發佈"
    new_status = "已發佈"
    items = fetch_database_items(database_id, filter_status)
    
    for item in items:
        page_id = item["id"]
        title = item["properties"]["title"]["title"][0]["text"]["content"]
        date = item["properties"]["date"]["date"]["start"] if item["properties"]["date"]["date"] else datetime.now().isoformat()
        tags = ', '.join(tag["name"] for tag in item["properties"]["tags"]["multi_select"]) if item["properties"]["tags"]["multi_select"] else "null"
        categories = ', '.join(cat["name"] for cat in item["properties"]["categories"]["multi_select"]) if item["properties"]["categories"]["multi_select"] else "null"
        index_img_url = item["properties"]["index_img"]["files"][0]["file"]["url"] if item["properties"]["index_img"]["files"] else None
        
        # Generate SEO-friendly URL name
        url_name = generate_seo_url_name(title, tags)
        
        # Directory for index image
        index_img_dir = "./themes/fluid/source/img"
        os.makedirs(index_img_dir, exist_ok=True)
        
        # Download index image
        index_img_path = None
        if index_img_url:
            index_img_name = f"{title.replace(' ', '_')}_index.webp"
            index_img_path = download_image_as_webp(index_img_url, index_img_name, index_img_dir)
            index_img_path = f"/img/{os.path.basename(index_img_path)}" if index_img_path else default_image_path
        else:
            index_img_path = default_image_path

        # Directory for other post images
        post_dir = f"./source/_posts/{title.replace(' ', '_')}"
        os.makedirs(post_dir, exist_ok=True)

        blocks = fetch_page_content(page_id)
        markdown_content = convert_to_markdown(title, date, tags, categories, index_img_path, blocks, post_dir, url_name)
        save_markdown_file(title, markdown_content)
        print(f"Saved: {title}")
        
        # Update status to "已發佈"
        update_page_status(page_id, new_status)
        print(f"Updated status for {title} to {new_status}")

if __name__ == "__main__":
    main()

