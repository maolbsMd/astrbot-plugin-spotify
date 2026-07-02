import os
import json
import re
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from astrbot.api.all import *
from astrbot.api.event import filter

@register("astrbot_plugin_spotify", "maolbsMd", "Spotify 智能点歌与控制插件", "1.1.0")
class SpotifyController(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.sp = None
        self.auth_manager = None
        
        if config:
            self.config = config
        else:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception:
                self.config = {}
                
        # 初始化 Spotify
        self._init_spotify()

    def _init_spotify(self):
        """真正的配置加载逻辑，不再去读死文件，而是读内存里的 config 字典"""
        client_id = self.config.get("client_id", "").strip()
        client_secret = self.config.get("client_secret", "").strip()
        redirect_uri = self.config.get("redirect_uri", "http://127.0.0.1:6198/callback").strip()
        
        # 清理用户从 WebUI 复制时可能带入的 Markdown 乱码
        if "[" in redirect_uri or "]" in redirect_uri:
            match = re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', redirect_uri)
            if match:
                redirect_uri = match.group(0)
        
        # 检查是否还是占位符
        if not client_id or not client_secret or client_id == "你的_CLIENT_ID" or client_id == "YOUR_SPOTIFY_CLIENT_ID":
            return
            
        scope = "user-modify-playback-state user-read-playback-state user-library-modify"
        self.auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            open_browser=False 
        )
        
        token_info = self.auth_manager.validate_token(self.auth_manager.cache_handler.get_cached_token())
        if token_info:
            self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
        else:
            self.sp = None

    # ================= 供人类用户使用的授权指令 =================

    @filter.command("spotify登录")
    async def spotify_login(self, event: AstrMessageEvent):
        """生成授权链接发给用户"""
        if not self.auth_manager:
            yield event.plain_result("请先在 WebUI 面板中填入完整的 client_id 和 client_secret。")
            return
            
        auth_url = self.auth_manager.get_authorize_url()
        
        msg = (
            "🎸 **Spotify 首次授权指南**\n"
            "1. 请在浏览器中点击（或复制打开）以下链接：\n"
            f"{auth_url}\n\n"
            "2. 登录并同意授权。\n"
            "3. 授权后，网页会跳转并显示『无法访问此网站』，这是正常的！\n"
            "4. 请复制此时浏览器地址栏里的**完整链接**。\n"
            "5. 回复我：`/spotify授权 <你复制的链接>`"
        )
        yield event.plain_result(msg)

    @filter.command("spotify授权")
    async def spotify_auth_callback(self, event: AstrMessageEvent, url: str):
        """接收用户的跳转链接并生成缓存"""
        if not self.auth_manager:
            yield event.plain_result("配置未完成，无法授权。")
            return
            
        try:
            # 从用户发来的 URL 中提取 code
            code = self.auth_manager.parse_response_code(url)
            if not code:
                yield event.plain_result("授权失败：提取不到 code，请确保复制了完整的链接。")
                return
                
            # 用 code 换取真实的 Token
            self.auth_manager.get_access_token(code)
            
            # 重新初始化 Spotify 客户端
            self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
            yield event.plain_result("✅ 授权成功！你的 Spotify 已经与 Bot 连接，现在可以开始点歌了！")
            
        except Exception as e:
            yield event.plain_result(f"❌ 授权过程中出错：{str(e)}")

# ================= Bot 自主调用的 LLM Tools =================

    @llm_tool(name="check_current_status")
    async def check_current_status(self, event: AstrMessageEvent) -> str:
        """
        Spotify 全能状态雷达。
        Bot 操作指南：获取当前所有可用设备（包含音量、类型）、当前正在播放的歌曲信息、进度、播放/暂停状态以及循环/随机模式。
        在执行播放控制或回答用户“我在听什么”、“音量多大”时调用此工具。
        """
        if not self.sp:
            return "Spotify 未授权，请提示用户先发送 /spotify登录。"
            
        try:
            # 1. 获取设备信息
            devices_res = self.sp.devices()
            devices = devices_res.get('devices', [])
            
            # 2. 获取当前播放状态
            playback_res = self.sp.current_playback()
            
            status_report = "📡 【Spotify 状态雷达报告】\n\n"
            
            if not devices:
                return status_report + "⚠️ 当前没有任何可用的设备在线。请提醒用户打开手机或电脑的 Spotify 客户端。"
            
            # 汇总设备信息
            status_report += "💻 [设备列表]:\n"
            for d in devices:
                active_mark = "🟢(活跃)" if d.get('is_active') else "⚪(休眠)"
                vol = d.get('volume_percent', '未知')
                d_type = d.get('type', '未知类型')
                d_name = d.get('name', '未知设备')
                status_report += f"  - {d_name} [{d_type}] {active_mark} | 音量: {vol}%\n"
                
            status_report += "\n🎵 [当前播放状态]:\n"
            if playback_res and playback_res.get('item'):
                is_playing = "▶️ 播放中" if playback_res.get('is_playing') else "⏸️ 已暂停"
                item = playback_res['item']
                
                song_name = item['name']
                artist_name = item['artists'][0]['name'] if item.get('artists') else "未知歌手"
                
                # 毫秒转换为秒
                progress_sec = playback_res.get('progress_ms', 0) // 1000
                duration_sec = item.get('duration_ms', 0) // 1000
                
                shuffle_state = "开启" if playback_res.get('shuffle_state') else "关闭"
                repeat_state = playback_res.get('repeat_state', 'off')
                
                status_report += f"  状态: {is_playing}\n"
                status_report += f"  歌曲: {song_name} - {artist_name}\n"
                status_report += f"  进度: {progress_sec}秒 / {duration_sec}秒\n"
                status_report += f"  模式: 随机[{shuffle_state}] | 循环[{repeat_state}]\n"
                
                # 检查是否在听特定的歌单
                context = playback_res.get('context')
                if context and context.get('type') == 'playlist':
                    status_report += f"  上下文: 正在播放某个歌单\n"
            else:
                status_report += "  当前没有歌曲在播放队列中，或设备处于完全闲置状态。\n"
                
            return status_report
            
        except Exception as e:
            return f"状态获取失败：{str(e)}"

    @llm_tool(name="search_spotify_library")
    async def search_spotify_library(self, event: AstrMessageEvent, keyword: str, search_type: str = "track", limit: int = 5) -> str:
        """
        Spotify 核心搜索雷达。向大模型提供精准或宽泛的搜索结果。
        参数 keyword: 搜索关键词（如 "周杰伦 晴天"、"运动歌单"）。
        参数 search_type: 搜索类型。可选值："track" (单曲, 默认), "playlist" (歌单), "artist" (歌手)。
        参数 limit: 返回结果的数量（1 到 50 之间的整数）。Bot 决策建议：
            - 若用户指令非常明确（如精准点歌），将 limit 设为 1~3 即可，提高响应速度。
            - 若用户指令宽泛模糊（如“推荐几首好听的纯音乐”），将 limit 设为 15~20，以便为你提供足够的挑选空间。
        Bot 操作指南：调用此工具后，请仔细比对返回的结果。注意区分原唱、翻唱、Live版等，挑选出最精准匹配用户需求的一项，提取其 URI，再调用 manage_playback 进行操作。
        """
        if not self.sp:
            return "Spotify 未授权。"
            
        # 强制保护，防止大模型抽风传入超过 50 的数值报错
        limit = max(1, min(limit, 50))
            
        try:
            results = self.sp.search(q=keyword, limit=limit, type=search_type)
            response_text = f"🎵 '{keyword}' 的 {search_type} 搜索结果 (共请求 {limit} 条)：\n"
            
            if search_type == "track":
                items = results['tracks']['items']
                if not items: return "没有找到相关单曲。"
                for i, item in enumerate(items):
                    name = item['name']
                    artist = item['artists'][0]['name']
                    uri = item['uri']
                    response_text += f"{i+1}. {name} - {artist} [{uri}]\n"
                    
            elif search_type == "playlist":
                items = results['playlists']['items']
                if not items: return "没有找到相关歌单。"
                for i, item in enumerate(items):
                    name = item['name']
                    owner = item['owner']['display_name']
                    uri = item['uri']
                    response_text += f"{i+1}. {name} (创建者:{owner}) [{uri}]\n"
                    
            return response_text
        except Exception as e:
            return f"搜索失败：{str(e)}"

    @llm_tool(name="manage_playback")
    async def manage_playback(self, event: AstrMessageEvent, action: str, uri: str = "", value: int = -1, state: str = "") -> str:
        """
        Spotify 核心播放控制中枢。
        参数 action: 必须是以下之一：
            - "play": 播放。有 uri 则放指定歌曲/歌单；无 uri 则恢复播放。
            - "queue": 排队。将指定的 uri 加入稍后播放队列。
            - "pause": 暂停。
            - "next": 下一首。
            - "previous": 上一首。
            - "seek": 调整进度。必须提供 value 参数（目标进度的毫秒数，例如 1 分钟处为 60000）。
            - "volume": 调节音量。必须提供 value 参数（0 到 100 之间的整数）。
            - "shuffle": 随机播放。必须提供 state 参数（"true" 开启，"false" 关闭）。
            - "repeat": 循环模式。必须提供 state 参数（"track" 单曲循环, "context" 列表循环, "off" 关闭）。
        """
        if not self.sp:
            return "Spotify 未授权。"
            
        try:
            if action == "play":
                if uri:
                    self.sp.start_playback(uris=[uri] if "track" in uri else None, context_uri=uri if "playlist" in uri or "album" in uri else None)
                    return f"已成功发送播放指令！目标 URI: {uri}"
                else:
                    self.sp.start_playback()
                    return "已恢复播放。"
            elif action == "queue":
                if not uri: return "排队失败：必须提供歌曲的 URI。"
                self.sp.add_to_queue(uri)
                return f"已成功将 URI: {uri} 加入播放队尾。"
            elif action == "pause":
                self.sp.pause_playback()
                return "音乐已暂停。"
            elif action == "next":
                self.sp.next_track()
                return "已切换到下一首。"
            elif action == "previous":
                self.sp.previous_track()
                return "已切换到上一首。"
            elif action == "seek":
                if value < 0: return "调整进度失败：缺少有效的 value 参数（毫秒）。"
                self.sp.seek_track(value)
                return f"已将播放进度调整至 {value / 1000} 秒处。"
            elif action == "volume":
                if not (0 <= value <= 100): return "音量调节失败：音量值必须在 0 到 100 之间。"
                self.sp.volume(value)
                return f"音量已调整为 {value}%。"
            elif action == "shuffle":
                shuffle_state = True if state.lower() == "true" else False
                self.sp.shuffle(shuffle_state)
                return f"随机播放已{'开启' if shuffle_state else '关闭'}。"
            elif action == "repeat":
                if state not in ["track", "context", "off"]: return "循环模式失败：state 必须为 track, context 或 off。"
                self.sp.repeat(state)
                return f"循环模式已设置为：{state}。"
            else:
                return f"未知的操作指令：{action}"
        except spotipy.exceptions.SpotifyException as e:
            if "NO_ACTIVE_DEVICE" in str(e):
                return "操作失败：没有找到活跃的 Spotify 设备。"
            return f"控制失败：Spotify API 报错 {str(e)}"
        except Exception as e:
            return f"执行控制时发生未知错误：{str(e)}"

    @llm_tool(name="save_track_spotify")
    async def save_track_spotify(self, event: AstrMessageEvent, uri: str) -> str:
        """
        一键收藏功能。将指定的歌曲加入用户的 '喜欢的音乐' 列表中。
        参数 uri: 歌曲的 URI。
        """
        if not self.sp:
            return "Spotify 未初始化。"
        try:
            self.sp.current_user_saved_tracks_add(tracks=[uri])
            return "✅ 已成功加入用户的 Spotify 收藏夹！"
        except Exception as e:
            return f"收藏失败：{str(e)}"
