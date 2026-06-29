# AstrBot-Plugin-Spotify 🎵

这是一个为 AstrBot 开发的 Spotify 智能点歌与控制插件。它赋予了你的 AI Agent 直接搜索音乐、控制设备播放、切歌以及收藏歌曲的能力，彻底解放双手，实现真正的自然语言点歌体验。

**作者**: maolbsMd
**版本**: 1.0.0

---

## ✨ 核心特性

- **🧠 智能搜索与判断**：Bot 会根据用户的自然语言需求，自动搜索 Spotify 曲库，并挑选最匹配的歌曲进行播放。
- **🎮 全面播放控制**：支持播放、暂停、上一首、下一首。
- **❤️ 一键收藏**：遇到好听的歌，直接告诉 Bot “把这首歌加入收藏”，即可同步到你的 Spotify「已点赞的歌曲」。
- **☁️ 云服务器友好**：内置手动授权流（Manual Auth Flow），完美适配无图形界面的 Linux 云服务器/Docker 容器部署，无需担心浏览器弹窗导致程序卡死。

---

## 🛠️ 安装与配置指南

### 第一步：获取 Spotify 开发者凭证
1. 访问 [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) 并登录你的 Spotify 账号（**必须是 Premium 高级会员账号**）。
2. 点击右上角的 `Create app` 创建一个新应用。
3. 填写基本信息后，进入该 App 的页面，点击 `Settings`。
4. **【⚠️ 最重要的一步】** 找到 **Redirect URIs**，准确无误地填入以下地址并保存：
   ```text
   [http://127.0.0.1:6198/callback](http://127.0.0.1:6198/callback)
