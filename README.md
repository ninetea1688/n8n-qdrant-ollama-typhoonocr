# N8N Typhoon OCR

โปรเจคนี้เป็นการรวม services ต่างๆ สำหรับการทำงานกับ N8N, OCR และ AI โดยใช้ Docker Compose

## Services ที่ใช้

- **N8N**: Workflow automation platform
- **PostgreSQL**: ฐานข้อมูลสำหรับ N8N
- **Ollama**: Local LLM สำหรับการประมวลผลภาษา
- **Qdrant**: Vector database สำหรับการค้นหาแบบ semantic
- **OpenTyphoon OCR**: Enhanced OCR engine with pre-processing and layout analysis.
- **Chunker Service**: A service to chunk and embed text.
- **Retrieval Service**: A service for advanced search in Qdrant.
- **Chat UI**: A Streamlit-based chat interface for interacting with the RAG pipeline.

## การติดตั้ง

1. ติดตั้ง Docker และ Docker Compose
2. Clone repository นี้
3. คัดลอกไฟล์ .env.example เป็น .env และตั้งค่า TYPHOON_OCR_API_KEY
4. รันคำสั่งเพื่อเริ่ม services:

```bash
docker-compose up -d
```

## การเข้าถึง Services

- **N8N**: http://localhost:5678
- **Ollama API**: http://localhost:11434
- **Qdrant API**: http://localhost:6333
- **Qdrant Dashboard**: http://localhost:6334
- **OpenTyphoon OCR**: http://localhost:8000
- **Chunker Service**: http://localhost:8001
- **Retrieval Service**: http://localhost:8002
- **Chat UI**: http://localhost:8501

## Chat UI

A simple web interface is provided to chat with your RAG system.

### **Important Setup Step**

Before using the Chat UI, you **must** configure it to point to your n8n workflow.

1.  **Create a Retrieval Workflow in n8n:** Use the `n8n_retrieval_workflow_guide.md` guide to build this workflow.
2.  **Set the Start Node to "Webhook":** The first node in this workflow must be a `Webhook` node.
3.  **Get the Webhook URL:** Copy the "Test URL" from the n8n Webhook node.
4.  **Update the Chat UI Code:**
    *   Open the file `chat-ui/app.py`.
    *   Find the line `N8N_WEBHOOK_URL = "YOUR_N8N_RETRIEVAL_WORKFLOW_WEBHOOK_URL_HERE"`.
    *   Replace the placeholder URL with the actual URL you copied from n8n.
5.  Restart the `chat-ui` service if it's already running: `docker compose restart chat-ui`

## การตั้งค่า

### N8N

- Host: localhost (สามารถเปลี่ยนได้ผ่าน N8N_HOST)
- Port: 5678
- Protocol: http (สามารถเปลี่ยนได้ผ่าน N8N_PROTOCOL)
- สามารถใช้งาน Typhoon OCR ผ่าน Custom Node

### PostgreSQL

- Database: n8n
- Username: n8n
- Password: n8n
- Port: 5432 (internal)

### Ollama

- Port: 11434
- ข้อมูลโมเดลจะถูกเก็บใน volume `ollama_data`

### Qdrant

- API Port: 6333
- Dashboard Port: 6334
- ข้อมูลจะถูกเก็บใน volume `qdrant_data`

#### การสร้าง Collection ใน Qdrant

1. ผ่าน Dashboard (http://localhost:6334):

   - คลิก "Create Collection"
   - ตั้งชื่อ collection
   - เลือก Vector Size (ตามขนาดของ vector ที่จะเก็บ)
   - เลือก Distance Metric (Cosine, Euclidean, หรือ Dot)
   - คลิก "Create"

2. ผ่าน API:

```bash
curl -X PUT 'http://localhost:6333/collections/my_collection' \
  -H 'Content-Type: application/json' \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    }
  }'
```

3. ตัวอย่างการใช้งานใน N8N:

```json
{
  "method": "PUT",
  "url": "http://qdrant:6333/collections/my_collection",
  "authentication": "none",
  "body": {
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    }
  }
}
```

4. การตรวจสอบ collection ที่มีอยู่:

```bash
curl 'http://localhost:6333/collections'
```

5. การลบ collection:

```bash
curl -X DELETE 'http://localhost:6333/collections/my_collection'
```

### OpenTyphoon OCR

- Port: 8000
- ต้องการ API Key จาก OpenTyphoon.ai (ตั้งค่าใน .env)
- รองรับการประมวลผลไฟล์ PDF และรูปภาพ
- มีการติดตั้ง poppler-utils สำหรับการประมวลผล PDF
- มีระบบ logging แสดงเวลาที่ใช้ในการประมวลผล

## การใช้งาน Typhoon OCR API

### การตั้งค่า API Key

ตั้งค่า API Key ในไฟล์ `.env`:

```env
TYPHOON_OCR_API_KEY=your_api_key_here
```

### การประมวลผลเอกสาร

```bash
curl -X POST "http://localhost:8000/process" \
  -F "file=@document.pdf" \
  -F "page_num=1" \
  -F "task_type=default"
```

Parameters:

- `file`: ไฟล์ที่ต้องการประมวลผล (PDF หรือรูปภาพ)
- `page_num`: หน้าที่ต้องการประมวลผล (ค่าเริ่มต้น: 1)
- `task_type`: ประเภทงาน (ค่าเริ่มต้น: "default")

### ตรวจสอบสถานะ API

```bash
curl "http://localhost:8000/health"
```

### รูปแบบผลลัพธ์

```json
{
  "result": "ข้อความที่ได้จากการประมวลผล OCR",
  "processing_time": {
    "minutes": 1,
    "seconds": 30,
    "total_seconds": 90.5
  }
}
```

## การใช้งาน Typhoon OCR ใน N8N

### การติดตั้ง Custom Node

1. เปิด N8N ที่ http://localhost:5678
2. ไปที่ Settings > Community Nodes
3. คลิก "Install a community node"
4. ใส่ URL ของ repository นี้
5. คลิก "Install"

### การใช้งานใน Workflow

1. เพิ่ม node "Typhoon OCR" ใน workflow
2. เลือก Operation:
   - Process Document: สำหรับประมวลผลเอกสาร
3. ตั้งค่าพารามิเตอร์:
   - File: URL หรือ base64 ของไฟล์ที่ต้องการประมวลผล

### ตัวอย่างการใช้งานใน N8N

#### 1. การประมวลผลไฟล์จาก URL

1. เพิ่ม node "HTTP Request" เพื่อดาวน์โหลดไฟล์
2. เพิ่ม node "Typhoon OCR" เพื่อประมวลผล
3. ตั้งค่า:
   - File: URL ของไฟล์

#### 2. การประมวลผลไฟล์จาก Form

1. เพิ่ม node "Webhook" เพื่อรับไฟล์จาก form
2. เพิ่ม node "Typhoon OCR" เพื่อประมวลผล
3. ตั้งค่า:
   - File: ข้อมูลไฟล์จาก form

#### 3. การประมวลผลหลายหน้า PDF

1. เพิ่ม node "HTTP Request" เพื่อดาวน์โหลด PDF
2. เพิ่ม node "Function" เพื่อวนลูปแต่ละหน้า
3. เพิ่ม node "Typhoon OCR" เพื่อประมวลผลแต่ละหน้า

## Volumes

- `n8n_data`: เก็บข้อมูลการตั้งค่าและ workflows ของ N8N
- `postgres_data`: เก็บข้อมูล PostgreSQL
- `ollama_data`: เก็บโมเดลและข้อมูลของ Ollama
- `qdrant_data`: เก็บข้อมูล vector ของ Qdrant
- `typhoon_ocr_data`: เก็บข้อมูลและไฟล์ที่ประมวลผลด้วย OCR

## การหยุด Services

```bash
docker-compose down
```

หากต้องการลบข้อมูลทั้งหมด (volumes) ให้ใช้คำสั่ง:

```bash
docker-compose down -v
```
