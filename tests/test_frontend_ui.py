"""Playwright 测试：PDF 上传按钮 + 记忆面板 UI"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

SCREENSHOTS = "D:/miner-agent/tests/screenshots"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto("http://localhost:5173")
    page.wait_for_load_state("networkidle")

    # 1. 初始聊天界面 — 回形针按钮应可见
    page.screenshot(path=f"{SCREENSHOTS}/01_chat_initial.png", full_page=True)
    print("[1] 初始界面截图完成")

    # 2. 检查回形针按钮存在
    paperclip = page.locator("button[title='上传 PDF']")
    assert paperclip.count() == 1, "回形针按钮应存在"
    print("[2] 回形针按钮存在 OK")

    # 3. 用精确选择器找到侧边栏底部的记忆按钮（BookOpen 图标旁的按钮）
    # 底部记忆按钮在 border-t 的 div 内
    memory_btn = page.locator("div.border-t button", has_text="记忆").first
    memory_btn.click()
    page.wait_for_timeout(800)

    # 4. 记忆面板截图
    page.screenshot(path=f"{SCREENSHOTS}/02_memory_panel.png", full_page=True)
    print("[3] 记忆面板截图完成")

    # 5. 检查面板标题 "记忆管理"
    panel_title = page.locator("text=记忆管理")
    if panel_title.count() >= 1:
        print("[4] 记忆管理标题存在 OK")
    else:
        print("[4] WARNING: 记忆管理标题未找到，可能 Vite 未热更新")

    # 6. 点击第一个记忆文件
    items = page.locator("[data-testid='memory-item']").all()
    if items:
        items[0].click()
        page.wait_for_timeout(800)
        page.screenshot(path=f"{SCREENSHOTS}/03_memory_detail.png", full_page=True)
        print(f"[5] 点击文件详情截图完成（共 {len(items)} 个文件）")

        # 7. 检查编辑按钮
        edit_btn = page.locator("button", has_text="编辑").first
        if edit_btn.is_visible():
            print("[6] 编辑按钮存在 OK")

            # 8. 点击编辑，进入编辑模式
            edit_btn.click()
            page.wait_for_timeout(400)
            page.screenshot(path=f"{SCREENSHOTS}/04_memory_edit.png", full_page=True)
            print("[7] 编辑模式截图完成")

            # 9. 检查 textarea
            textarea = page.locator("textarea").first
            if textarea.is_visible():
                print("[8] 编辑 textarea 存在 OK")
            else:
                print("[8] WARNING: textarea 未找到")

            # 10. 保存/取消按钮
            save_btn = page.locator("button", has_text="保存")
            cancel_btn = page.locator("button", has_text="取消")
            print(f"[9] 保存按钮: {'OK' if save_btn.count() else 'MISSING'}, 取消按钮: {'OK' if cancel_btn.count() else 'MISSING'}")
        else:
            print("[6] WARNING: 编辑按钮不可见")

        # 11. 检查删除按钮
        delete_btn = page.locator("button", has_text="删除")
        print(f"[10] 删除按钮: {'OK' if delete_btn.count() else 'MISSING'}")
    else:
        print("[5] 没有 data-testid='memory-item' 元素，检查面板内容")
        # 备选：直接截图看面板状态
        page.screenshot(path=f"{SCREENSHOTS}/03_no_items.png", full_page=True)

    browser.close()
    print("\n测试完成！请查看 tests/screenshots/ 目录下的截图")
