import unittest
from flask import Flask
from main import app

class TestFlaskApp(unittest.TestCase):

    def setUp(self):
        """在每个测试之前运行，创建一个测试客户端"""
        self.app = app.test_client()
        self.app.testing = True

    def test_main_page(self):
        """测试主页面"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_clear_files(self):
        """测试清除文件功能"""
        response = self.app.get('/clear?filename=testfile.txt')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Delete", response.data)

    def test_get_picture(self):
        """测试获取图片功能"""
        response = self.app.get('/getpicture?name=testfile.jpg')
        self.assertEqual(response.status_code, 404)  # 假设文件不存在
        self.assertIn(b"File does not exist", response.data)

    def test_test_connection(self):
        """测试连接检测"""
        response = self.app.get('/test')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You already connect the server now!", response.data)

if __name__ == "__main__":
    unittest.main()
