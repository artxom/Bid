from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_root():
    """测试 API 根路径是否正常运行"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Bid Assistant API is running"}

def test_upload_endpoint_exists():
    """测试上传接口是否存在并能接收文件"""
    # 创建一个模拟的 docx 文件内容
    files = {"file": ("test.docx", b"fake-docx-content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    response = client.post("/upload", files=files)
    assert response.status_code == 200
    assert response.json()["filename"] == "test.docx"
