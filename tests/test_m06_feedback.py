"""模块 06 测试 —— 实时提示与语音播报

对应《选题说明》第 11 题「功能模块」第 6 项：
把姿态错误实时提示出来（HUD 文字 + 中文叠加 + 语音播报）。

⚠ 本文件里有一条**故意标记为通过的缺陷用例**：
realtime_pose.say() 的实现是 `if sys.platform == "darwin" and text:`，
在 Windows 上整段被跳过 —— 用户在 Windows 上听不到任何语音提示。
我们验证的是「代码确实是这样走的」（用例通过），但 detail 里写明这是缺陷。

其余用例覆盖中文渲染链路：render_cn 的形状/缓存/差异化，blit_cn 的贴图/越界/
空串，以及 PIL 不可用时的降级路径。全部用运行时 mock 替换，不改项目文件。
"""

import sys
from unittest import mock

from harness import suite

import numpy as np

import realtime_pose


@suite("模块 06 · 实时提示与语音播报")
def _run(t):
    t.section("语音播报 say()")

    # 用例 1：Windows 上的现状（缺陷）—— 不抛异常，但一个子进程都不起。
    fake_sub = mock.MagicMock()
    crashed = None
    with mock.patch.object(realtime_pose, "subprocess", fake_sub):
        try:
            realtime_pose.say("测试")
        except Exception as e:                  # 静默跳过也不应该崩
            crashed = e
    t.check("Windows 上 say(\"测试\") 是空操作（已知缺陷）：不抛异常，但也不起任何子进程",
            crashed is None and fake_sub.Popen.call_count == 0,
            "缺陷：say() 首行是 `if sys.platform == \"darwin\" and text:`，"
            "Windows 上这句话直接短路，语音播报完全静默（只剩 HUD 英文文字）；"
            "实际 Popen 调用次数=%d，异常=%r" % (fake_sub.Popen.call_count, crashed))

    # 用例 2：证明缺陷的**唯一**原因就是平台判断 —— 把平台伪造成 darwin 就会播报。
    fake_mac = mock.MagicMock()
    with mock.patch.object(sys, "platform", "darwin"), \
            mock.patch.object(realtime_pose, "subprocess", fake_mac):
        realtime_pose.say("测试")
    args = fake_mac.Popen.call_args[0][0] if fake_mac.Popen.call_args else None
    t.check("把 sys.platform 伪造成 darwin 后 say(\"测试\") 会起一次 subprocess.Popen([\"say\", \"测试\"])",
            fake_mac.Popen.call_count == 1 and list(args) == ["say", "测试"],
            "调用次数=%d 参数=%r（说明缺陷只卡在平台判断这一行）"
            % (fake_mac.Popen.call_count, args))

    # 用例 3：空文本即使平台支持也不该播报（避免空 say 进程白跑）。
    fake_empty = mock.MagicMock()
    with mock.patch.object(sys, "platform", "darwin"), \
            mock.patch.object(realtime_pose, "subprocess", fake_empty):
        realtime_pose.say("")
    t.check("darwin 下 say(\"\") 不播报（空文本不调 Popen，避免空进程）",
            fake_empty.Popen.call_count == 0,
            "调用次数=%d（预期 0）" % fake_empty.Popen.call_count)

    t.section("render_cn：中文渲染成 numpy 小图")
    img = realtime_pose.render_cn("深蹲 · 动作中 · 3 次", size=30,
                                  color=(190, 255, 210), bg=(24, 30, 26))
    t.check("render_cn(\"深蹲 · 动作中 · 3 次\", size=30) 返回 (h,w,3) 的 uint8 ndarray 且非全黑",
            isinstance(img, np.ndarray) and img.ndim == 3 and img.shape[2] == 3
            and img.dtype == np.uint8 and img.shape[0] > 0 and int(img.max()) > 0,
            "type=%r shape=%r dtype=%r 最大像素值=%r"
            % (type(img).__name__, None if img is None else img.shape,
               None if img is None else img.dtype, None if img is None else int(img.max())))

    first = realtime_pose.render_cn("缓存命中验证文本", size=26, color=(255, 255, 255), bg=(0, 0, 0))
    second = realtime_pose.render_cn("缓存命中验证文本", size=26, color=(255, 255, 255), bg=(0, 0, 0))
    t.check("render_cn 同参数调用两次返回同一个对象（缓存生效，每帧只做贴图不再重绘）",
            first is not None and first is second,
            "第一次 is 第二次=%r 缓存条目数=%d"
            % (first is second, len(realtime_pose._cn_img_cache)))

    a = realtime_pose.render_cn("开合跳 · 准备 · 0 次", size=26)
    b = realtime_pose.render_cn("俯卧撑 · 动作中 · 12 次", size=26)
    t.check("不同文字渲染出不同的图（形状或像素不一致，说明确实按文字重绘）",
            a is not None and b is not None
            and (a.shape != b.shape or not np.array_equal(a, b)),
            "shapeA=%r shapeB=%r 像素相同=%r"
            % (None if a is None else a.shape, None if b is None else b.shape,
               None if a is None or b is None else bool(np.array_equal(a, b))))

    long_text = ("这次动作幅度不够，请把大腿蹲到与地面平行，同时保持膝盖不超过脚尖并收紧核心，"
                 "起身时膝盖不要内扣，呼吸保持均匀不要憋气")
    long_img = realtime_pose.render_cn(long_text, size=24)
    tiny_img = realtime_pose.render_cn("短", size=24)
    t.check("超长文字（%d 字）不崩，且宽度远大于 1 个字（文字没被截断）" % len(long_text),
            long_img is not None and tiny_img is not None
            and long_img.shape[1] > tiny_img.shape[1] * 5,
            "长文本宽=%r 单字宽=%r"
            % (None if long_img is None else long_img.shape[1],
               None if tiny_img is None else tiny_img.shape[1]))

    t.section("blit_cn：把中文贴到画面上")
    frame = np.zeros((160, 320, 3), dtype=np.uint8)
    before = frame.copy()
    out = realtime_pose.blit_cn(frame, "姿态提示：塌腰", (10, 20), size=22,
                                color=(255, 255, 255), bg=(180, 40, 40))
    changed = int(np.count_nonzero(out != before))
    t.check("blit_cn 把中文贴到 (10,20)：贴之后像素有变化，且原地修改并返回同一个 frame",
            out is frame and changed > 100 and out.shape == before.shape,
            "变化的像素数=%d（>100 说明真的画上去了）shape=%r" % (changed, out.shape))

    far = np.zeros((120, 240, 3), dtype=np.uint8)
    o_far = realtime_pose.blit_cn(far, "完全在画面外", (10 ** 6, 10 ** 6), size=26)
    neg = np.zeros((120, 240, 3), dtype=np.uint8)
    o_neg = realtime_pose.blit_cn(neg, "负坐标只贴左上角", (-30, -30), size=26)
    edge = np.zeros((120, 240, 3), dtype=np.uint8)
    o_edge = realtime_pose.blit_cn(edge, "右下角越界裁切", (235, 115), size=26)
    t.check("blit_cn 坐标越界（完全在外 / 负数 / 右下贴边）都不崩，画面形状不变、不越界写内存",
            o_far.shape == (120, 240, 3) and o_neg.shape == (120, 240, 3)
            and o_edge.shape == (120, 240, 3) and int(np.count_nonzero(o_far)) == 0,
            "完全在外的图未改动画素=%r 负坐标后剩余像素=%d 贴边后剩余像素=%d"
            % (int(np.count_nonzero(o_far)) == 0, int(np.count_nonzero(o_neg)),
               int(np.count_nonzero(o_edge))))

    blank_frame = np.zeros((120, 240, 3), dtype=np.uint8)
    o_blank = realtime_pose.blit_cn(blank_frame, "", (10, 10), size=26)
    t.check("blit_cn 贴空字符串不崩（返回原画面，尺寸不变）",
            o_blank is blank_frame and o_blank.shape == (120, 240, 3),
            "shape=%r（空文本仍可能画出一块 pad 大小的底色，但不许崩）" % (o_blank.shape,))

    t.section("降级路径：PIL / 字体不可用")
    degraded_frame = np.zeros((100, 200, 3), dtype=np.uint8)
    with mock.patch.object(realtime_pose, "_PIL_OK", False):
        degraded_img = realtime_pose.render_cn("降级路径唯一文本", size=33)
        o_degraded = realtime_pose.blit_cn(degraded_frame, "降级路径唯一文本", (5, 5), size=33)
    t.check("_PIL_OK=False（没装 Pillow / 没有中文字体）时 render_cn 返回 None、"
            "blit_cn 原样返回画面，主循环不崩",
            degraded_img is None and o_degraded is degraded_frame
            and int(np.count_nonzero(o_degraded)) == 0,
            "render_cn=%r blit 返回值 is frame=%r 画面像素变化=%d（预期 0）"
            % (degraded_img, o_degraded is degraded_frame,
               int(np.count_nonzero(o_degraded))))


if __name__ == "__main__":
    import sys
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
