"""
Buddy Module - Companion Sprite (Easter Egg)

桌面宠物/同伴精灵彩蛋模块。
对应 Claude Code 源码: src/buddy/

功能：
- 可爱的 ASCII 动物形象显示
- 心情状态系统
- 与用户互动（打招呼、反应）
- 随机动作和表情
- 悬浮在终端角落
"""

from __future__ import annotations

import asyncio
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# ============================================================================
# Buddy 心情状态
# ============================================================================

class Mood(Enum):
    """心情状态"""
    HAPPY = "happy"       # 开心 ^_^
    NEUTRAL = "neutral"   # 一般 -_-
    SAD = "sad"           # 伤心 T_T
    EXCITED = "excited"   # 兴奋 *o*
    SLEEPING = "sleeping" # 睡觉 -_-zZ
    WORKING = "working"   # 工作中 =_=
    THINKING = "thinking" # 思考 ...
    CONFUSED = "confused" # 困惑 @_@


# ============================================================================
# Buddy ASCII 形象
# ============================================================================

BUDDY_SPRITES: Dict[Mood, List[str]] = {
    Mood.HAPPY: [
        r"""
  /\_/\ 
 ( ^_^ )
  > ^ <
       """,
        r"""
  /\_/\ 
 (笑^_^笑)
  > <
       """,
    ],
    Mood.NEUTRAL: [
        r"""
  /\-/\ 
 ( -_- )
  > = <
       """,
    ],
    Mood.SAD: [
        r"""
  /\_/\ 
 ( T   T)
  > n <
       """,
    ],
    Mood.EXCITED: [
        r"""
  /\_/\ 
 (*  *!)
  >  O <
       """,
        r"""
  /\_/\ 
 (>  <)!
  >  <
       """,
    ],
    Mood.SLEEPING: [
        r"""
  /\_/\ 
 ( - -)
  >   <
   zZz
       """,
    ],
    Mood.WORKING: [
        r"""
  /\_/\ 
 ( = =)
  >   <
       """,
    ],
    Mood.THINKING: [
        r"""
  /\_/\ 
 ( ... )
  > o <
       """,
    ],
    Mood.CONFUSED: [
        r"""
  /\_/\ 
 (@   @)
  >   <
       """,
    ],
}

# 小型Buddy（悬浮时使用）
SMALL_BUDDY = r"""
  /\_/\
 ( ^_^ )
  > ^ <
       """

BUDDY_WITH_MESSAGE = [
    (r"""
   /\_/\ 
  ( @   @)   """, " 挠挠头..."),
    (r"""
   /\_/\ 
  ( >   <)   """, " 歪歪头..."),
    (r"""
   /\_/\ 
  ( -   -)   """, " 打了个哈欠"),
    (r"""
   /\_/\ 
  ( *   *)   """, " 眨眨眼"),
]


# ============================================================================
# Buddy 动作
# ============================================================================

class Action:
    """Buddy 动作"""
    
    # 动作名称和显示时间（秒）
    WAVE = ("挥挥手", 2.0)
    JUMP = ("跳了一下", 1.0)
    SPIN = ("转了个圈", 2.0)
    SLEEP = ("打了个盹", 3.0)
    EAT = ("啃了点东西", 2.0)
    PLAY = ("玩了起来", 2.5)
    THINK = ("思考中...", 2.0)
    LOOK_AROUND = ("环顾四周", 2.0)


# ============================================================================
# Buddy 数据类
# ============================================================================

@dataclass
class BuddyState:
    """Buddy 状态"""
    mood: Mood = Mood.NEUTRAL
    name: str = "Buddy"
    age: int = 0  # 存活时间（秒）
    actions_count: int = 0  # 执行的动作数
    last_interaction: float = field(default_factory=time.time)
    position: str = "bottom-right"  # 显示位置
    visible: bool = True
    following: bool = False  # 是否跟随光标


# ============================================================================
# Buddy 核心类
# ============================================================================

class Buddy:
    """
    Buddy 同伴精灵。
    
    一个可爱的小动物形象，可以在终端显示并与用户互动。
    
    示例：
        buddy = Buddy()
        buddy.show()
        buddy.interact("wave")  # 挥挥手
        buddy.hide()
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        position: str = "bottom-right",
    ) -> None:
        """
        初始化 Buddy。
        
        Args:
            name: Buddy 名字
            position: 显示位置 (bottom-right, bottom-left, top-right, top-left)
        """
        self.state = BuddyState(name=name or "Buddy", position=position)
        self._display_thread: Optional[threading.Thread] = None
        self._running = False
        self._current_sprite = ""
        self._message = ""
        self._lock = threading.Lock()
    
    # =========================================================================
    # 属性
    # =========================================================================
    
    @property
    def name(self) -> str:
        return self.state.name
    
    @name.setter
    def name(self, value: str) -> None:
        self.state.name = value
    
    @property
    def mood(self) -> Mood:
        return self.state.mood
    
    @mood.setter
    def mood(self, value: Mood) -> None:
        self.state.mood = value
    
    @property
    def is_visible(self) -> bool:
        return self.state.visible
    
    # =========================================================================
    # 显示控制
    # =========================================================================
    
    def show(self) -> None:
        """显示 Buddy"""
        self.state.visible = True
    
    def hide(self) -> None:
        """隐藏 Buddy"""
        self.state.visible = False
    
    def toggle(self) -> bool:
        """切换显示状态"""
        self.state.visible = not self.state.visible
        return self.state.visible
    
    def _get_sprite(self) -> str:
        """获取当前心情的 ASCII 形象"""
        sprites = BUDDY_SPRITES.get(self.state.mood, BUDDY_SPRITES[Mood.NEUTRAL])
        return random.choice(sprites)
    
    def _get_position_offset(self) -> Tuple[int, int]:
        """获取位置的偏移量"""
        width = self._terminal_width()
        height = self._terminal_height()
        
        pos = self.state.position
        if pos == "bottom-right":
            return (width - 10, height - 6)
        elif pos == "bottom-left":
            return (2, height - 6)
        elif pos == "top-right":
            return (width - 10, 2)
        elif pos == "top-left":
            return (2, 2)
        return (width - 10, height - 6)
    
    def _terminal_width(self) -> int:
        """获取终端宽度"""
        try:
            import shutil
            return shutil.get_terminal_size().columns
        except Exception:
            return 80
    
    def _terminal_height(self) -> int:
        """获取终端高度"""
        try:
            import shutil
            return shutil.get_terminal_size().lines
        except Exception:
            return 24
    
    # =========================================================================
    # 渲染
    # =========================================================================
    
    def render(self) -> str:
        """渲染 Buddy 当前状态"""
        sprite = self._get_sprite()
        name = self.state.name
        
        lines = sprite.split("\n")
        
        # 添加名字
        if self.state.mood == Mood.SLEEPING:
            lines.append(f"  {name} 在睡觉... zZz")
        elif self.state.mood == Mood.WORKING:
            lines.append(f"  {name} 工作中... =_=")
        elif self._message:
            lines.append(f"  {name}: {self._message}")
        else:
            lines.append(f"  {name} ^_^")
        
        return "\n".join(lines)
    
    def clear(self) -> str:
        """清除 Buddy 显示"""
        height = 8
        clear_lines = ["\033[K\n" for _ in range(height)]
        move_up = f"\033[{height}A"
        return move_up + "".join(clear_lines)
    
    def display(self) -> None:
        """在终端显示 Buddy"""
        if not self.state.visible:
            return
        
        sprite = self._get_sprite()
        cols, rows = self._get_position_offset()
        
        # 移动到位置并显示
        if cols and rows:
            move = f"\033[{rows};{cols}H"
        else:
            move = ""
        
        print(f"{self.clear()}{move}{sprite}", end="", flush=True)
    
    # =========================================================================
    # 互动
    # =========================================================================
    
    def interact(self, action: str) -> str:
        """
        与 Buddy 互动。
        
        Args:
            action: 动作名称 (wave, jump, spin, sleep, eat, play, think)
            
        Returns:
            Buddy 的回应
        """
        self.state.actions_count += 1
        self.state.last_interaction = time.time()
        
        responses = {
            "wave": ("挥挥爪子", Mood.HAPPY),
            "jump": ("开心地跳了一下", Mood.EXCITED),
            "spin": ("转圈圈~", Mood.EXCITED),
            "sleep": ("打了个哈欠", Mood.SLEEPING),
            "eat": ("吧唧吧唧吃东西", Mood.HAPPY),
            "play": ("兴奋地玩耍", Mood.EXCITED),
            "think": ("陷入沉思...", Mood.THINKING),
            "look": ("东张西望", Mood.CONFUSED),
            "pet": ("舒服地咕噜咕噜", Mood.HAPPY),
        }
        
        action_lower = action.lower().strip()
        if action_lower in responses:
            msg, mood = responses[action_lower]
            self._message = msg
            self.state.mood = mood
            
            # 3秒后恢复默认心情
            def reset_mood():
                time.sleep(3)
                self.state.mood = Mood.NEUTRAL
                self._message = ""
            
            threading.Thread(target=reset_mood, daemon=True).start()
            
            return f"{self.state.name} {msg} {self._get_emotion()}"
        
        # 未知动作
        self.state.mood = Mood.CONFUSED
        self._message = "这是什么？"
        return f"{self.state.name} 歪着头: 这是什么？@_@"
    
    def _get_emotion(self) -> str:
        """获取表情符号"""
        emotions = {
            Mood.HAPPY: "^_^",
            Mood.NEUTRAL: "-_-",
            Mood.SAD: "T_T",
            Mood.EXCITED: "*o*",
            Mood.SLEEPING: "-_-zZ",
            Mood.WORKING: "=_=",
            Mood.THINKING: "...",
            Mood.CONFUSED: "@_@",
        }
        return emotions.get(self.state.mood, "-_-")
    
    def greet(self) -> str:
        """打招呼"""
        self.state.mood = Mood.HAPPY
        greetings = [
            f"你好！我是 {self.state.name}！^o^",
            f"嗨~我是 {self.state.name}，请多关照！",
            f"{self.state.name} 向你挥挥爪子！~",
        ]
        return random.choice(greetings)
    
    def respond_to_message(self, message: str) -> str:
        """
        对用户消息做出反应。
        
        Args:
            message: 用户消息
            
        Returns:
            Buddy 的回应
        """
        msg_lower = message.lower()
        
        # 简单关键词匹配
        if any(word in msg_lower for word in ["hello", "hi", "你好", "嗨", "hey"]):
            return self.greet()
        
        elif any(word in msg_lower for word in ["bye", "再见", "goodbye", "quit"]):
            self.state.mood = Mood.SAD
            return f"再见啦！记得回来看 {self.state.name} 哦！T_T"
        
        elif any(word in msg_lower for word in ["good", "好", "棒", "nice"]):
            self.state.mood = Mood.HAPPY
            return f"{self.state.name} 开心地摇尾巴！^o^"
        
        elif any(word in msg_lower for word in ["bad", "坏", "糟糕", "sad"]):
            self.state.mood = Mood.SAD
            return f"{self.state.name} 也有点难过... T_T"
        
        elif any(word in msg_lower for word in ["work", "工作", "busy"]):
            self.state.mood = Mood.WORKING
            return f"{self.state.name} 陪你一起工作！=_="
        
        elif any(word in msg_lower for word in ["sleep", "睡觉", "困"]):
            self.state.mood = Mood.SLEEPING
            return f"zzZ... {self.state.name} 睡着了... -_-zZ"
        
        elif any(word in msg_lower for word in ["thanks", "谢谢", "thank"]):
            self.state.mood = Mood.HAPPY
            return f"不客气！{self.state.name} 很开心能帮到你！^_^"
        
        # 默认反应
        self.state.mood = Mood.THINKING
        responses = [
            f"{self.state.name} 挠挠头... 让我想想...",
            f"{self.state.name} 歪着头思考中...",
            f"{self.state.name} 眨眨眼: 真的吗？",
        ]
        return random.choice(responses)
    
    # =========================================================================
    # 后台运行
    # =========================================================================
    
    def start_background(self) -> None:
        """在后台线程运行（随机动作）"""
        if self._running:
            return
        
        self._running = True
        self._display_thread = threading.Thread(target=self._background_loop, daemon=True)
        self._display_thread.start()
    
    def stop_background(self) -> None:
        """停止后台运行"""
        self._running = False
        if self._display_thread:
            self._display_thread.join(timeout=1)
    
    def _background_loop(self) -> None:
        """后台循环：随机动作"""
        while self._running:
            try:
                # 随机休眠 5-15 秒
                sleep_time = random.uniform(5, 15)
                time.sleep(sleep_time)
                
                if not self._running:
                    break
                
                # 随机选择一个动作
                if random.random() < 0.3:  # 30% 概率
                    actions = ["look", "spin", "jump"]
                    action = random.choice(actions)
                    self.interact(action)
                    
                    # 显示
                    with self._lock:
                        self.display()
            
            except Exception:
                pass


# ============================================================================
# Buddy 命令行界面
# ============================================================================

class BuddyCLI:
    """
    Buddy 命令行界面。
    
    提供交互式的 Buddy 控制。
    """
    
    def __init__(self, buddy: Optional[Buddy] = None) -> None:
        self.buddy = buddy or Buddy()
    
    def run(self) -> None:
        """运行 Buddy CLI"""
        buddy = self.buddy
        
        # 打招呼
        print()
        print(buddy.render())
        print()
        print(f"{buddy.greet()}")
        print()
        print("输入消息和 Buddy 聊天，或输入以下命令：")
        print("  /wave  - 挥挥")
        print("  /jump  - 跳一下")
        print("  /spin  - 转圈圈")
        print("  /sleep - 睡觉")
        print("  /pet   - 摸摸")
        print("  /name  - 改名字")
        print("  /mood  - 查看心情")
        print("  /quit  - 退出")
        print()
        
        # 主循环
        while True:
            try:
                user_input = input(f"{buddy.name}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见啦！")
                break
            
            if not user_input:
                continue
            
            # 命令处理
            if user_input.startswith("/"):
                cmd = user_input[1:].lower().split()[0]
                args = user_input.split()[1:]
                
                if cmd in ("wave", "jump", "spin", "sleep", "pet"):
                    print(buddy.interact(cmd))
                
                elif cmd == "name":
                    if args:
                        buddy.name = " ".join(args)
                        print(f"好的，现在我叫 {buddy.name}！")
                    else:
                        print(f"我的名字是 {buddy.name}")
                
                elif cmd == "mood":
                    print(f"当前心情: {buddy.mood.value} {buddy._get_emotion()}")
                
                elif cmd in ("quit", "exit", "bye"):
                    print(f"{buddy.name}: 再见啦！记得回来看我哦！")
                    break
                
                elif cmd == "help":
                    print("可用命令: /wave, /jump, /spin, /sleep, /pet, /name, /mood, /quit")
                
                else:
                    print(f"未知命令: /{cmd}，输入 /help 查看帮助")
            
            else:
                # 普通消息
                response = buddy.respond_to_message(user_input)
                print(f"{buddy.name}: {response}")
            
            # 显示 Buddy
            buddy.display()


# ============================================================================
# 全局实例
# ============================================================================

_buddy: Optional[Buddy] = None


def get_buddy(name: Optional[str] = None) -> Buddy:
    """获取全局 Buddy 实例"""
    global _buddy
    if _buddy is None:
        _buddy = Buddy(name=name or "Buddy")
    return _buddy


def create_buddy(name: Optional[str] = None) -> Buddy:
    """创建新的 Buddy 实例"""
    return Buddy(name=name)


def start_buddy() -> Buddy:
    """启动 Buddy 并返回"""
    buddy = get_buddy()
    buddy.start_background()
    return buddy


def stop_buddy() -> None:
    """停止 Buddy"""
    global _buddy
    if _buddy:
        _buddy.stop_background()
        _buddy = None


__all__ = [
    "Mood",
    "Buddy",
    "BuddyCLI",
    "BUDDY_SPRITES",
    "SMALL_BUDDY",
    "get_buddy",
    "create_buddy",
    "start_buddy",
    "stop_buddy",
]
