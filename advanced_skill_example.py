"""
高级技能系统使用示例

演示如何使用高级技能系统来创建基于条件的技能触发。
"""

import time
from advanced_skill_system import AdvancedSkill, TriggerCondition, KeyboardSimulator, advanced_skill_manager

def create_sample_skills():
    """创建示例技能"""
    print("创建示例技能...")
    
    # 创建一个基于颜色的技能
    skill1 = AdvancedSkill("血量低回复", "1", 0)
    skill1.cooldown = 30.0  # 30秒冷却
    
    # 创建一个颜色条件，例如检测红色血量条
    color_condition = TriggerCondition(
        name="低血量检测",
        condition_type="color",
        parameters={
            'x': 100,  # 屏幕上血量条的位置
            'y': 100,
            'color': [255, 0, 0],  # 红色
            'tolerance': 20  # 颜色匹配容差
        }
    )
    
    # 添加条件到技能
    skill1.add_condition(color_condition)
    
    # 添加技能到管理器
    advanced_skill_manager.add_skill(skill1)
    
    # 创建一个基于时间的技能
    skill2 = AdvancedSkill("定时增益", "2", 1)
    skill2.cooldown = 60.0  # 60秒冷却
    
    # 创建一个时间条件
    time_condition = TriggerCondition(
        name="定时触发",
        condition_type="time",
        parameters={
            'interval': 60.0  # 每60秒触发一次
        }
    )
    
    # 添加条件到技能
    skill2.add_condition(time_condition)
    
    # 添加技能到管理器
    advanced_skill_manager.add_skill(skill2)
    
    # 创建一个组合条件的技能
    skill3 = AdvancedSkill("复合技能", "3", 2)
    skill3.cooldown = 45.0  # 45秒冷却
    
    # 创建组合条件
    combo_condition = TriggerCondition(
        name="组合触发",
        condition_type="combo",
        parameters={
            'combo_type': 'AND'  # 需要所有子条件都满足
        }
    )
    
    # 创建子条件1：颜色检测
    sub_cond1 = TriggerCondition(
        name="目标检测",
        condition_type="color",
        parameters={
            'x': 300,
            'y': 200,
            'color': [0, 255, 0],  # 绿色
            'tolerance': 20
        }
    )
    
    # 创建子条件2：时间检测
    sub_cond2 = TriggerCondition(
        name="冷却检测",
        condition_type="time",
        parameters={
            'interval': 20.0  # 至少20秒间隔
        }
    )
    
    # 添加子条件到组合条件
    combo_condition.add_sub_condition(sub_cond1)
    combo_condition.add_sub_condition(sub_cond2)
    
    # 添加组合条件到技能
    skill3.add_condition(combo_condition)
    
    # 添加技能到管理器
    advanced_skill_manager.add_skill(skill3)
    
    # 创建一个按键序列技能
    skill4 = AdvancedSkill("连招", "4", 3)
    skill4.cooldown = 15.0  # 15秒冷却
    skill4.key_sequence = ["1", "2", "3"]  # 按键序列
    skill4.sequential_press = True  # 按顺序按下
    
    # 创建时间条件
    seq_condition = TriggerCondition(
        name="连招触发",
        condition_type="time",
        parameters={
            'interval': 15.0
        }
    )
    
    # 添加条件到技能
    skill4.add_condition(seq_condition)
    
    # 添加技能到管理器
    advanced_skill_manager.add_skill(skill4)
    
    print(f"创建了 {len(advanced_skill_manager.skills)} 个示例技能")

def test_skills():
    """测试技能系统"""
    print("启动技能循环，按Ctrl+F12停止...")
    
    # 设置热键
    advanced_skill_manager.set_hotkeys("ctrl+f11", "ctrl+f12")
    
    # 开始循环
    advanced_skill_manager.start_cycle()
    
    # 注册状态回调
    def on_status(status):
        print(f"状态: {status}")
    
    def on_skill_used(skill_name):
        print(f"使用技能: {skill_name}")
    
    advanced_skill_manager.signals.status_signal.connect(on_status)
    advanced_skill_manager.signals.skill_used_signal.connect(on_skill_used)
    
    # 保持程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("手动停止...")
    finally:
        # 停止循环
        advanced_skill_manager.stop_cycle()
        print("技能循环已停止")

if __name__ == "__main__":
    # 创建示例技能
    create_sample_skills()
    
    # 测试技能系统
    test_skills() 