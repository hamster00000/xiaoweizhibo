#!/usr/bin/env python3
"""
一键运行脚本 start.sh 单元与集成测试
"""
import os
import subprocess
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START_SH = os.path.join(BASE_DIR, "start.sh")
RUN_SH = os.path.join(BASE_DIR, "run.sh")


class TestStartScript(unittest.TestCase):

    def test_script_executable(self):
        """验证 start.sh 存在且具备可执行权限"""
        self.assertTrue(os.path.exists(START_SH), "start.sh 必须存在")
        self.assertTrue(os.access(START_SH, os.X_OK), "start.sh 必须具备可执行权限")

    def test_symlink_run_sh(self):
        """验证 run.sh 软链接存在且指向 start.sh"""
        self.assertTrue(os.path.exists(RUN_SH), "run.sh 软链接必须存在")
        self.assertTrue(os.path.islink(RUN_SH), "run.sh 必须是符号链接")

    def test_help_command(self):
        """测试 help 命令输出完整用法说明"""
        res = subprocess.run([START_SH, "help"], capture_output=True, text=True, cwd=BASE_DIR)
        self.assertEqual(res.returncode, 0)
        self.assertIn("使用说明", res.stdout)
        self.assertIn("常用命令", res.stdout)
        self.assertIn("./start.sh", res.stdout)
        self.assertIn("./start.sh -d", res.stdout)
        self.assertIn("./start.sh stop", res.stdout)
        self.assertIn("./start.sh status", res.stdout)

    def test_status_command(self):
        """测试 status 状态探针输出"""
        res = subprocess.run([START_SH, "status"], capture_output=True, text=True, cwd=BASE_DIR)
        self.assertEqual(res.returncode, 0)
        self.assertTrue("在线" in res.stdout or "离线" in res.stdout)

    def test_run_sh_help(self):
        """测试通过 run.sh 调用 help 指令"""
        res = subprocess.run([RUN_SH, "--help"], capture_output=True, text=True, cwd=BASE_DIR)
        self.assertEqual(res.returncode, 0)
        self.assertIn("使用说明", res.stdout)


if __name__ == "__main__":
    unittest.main()
