// 实体手柄四个面键 → 游戏键：系统（GameController）给的 buttonA/B/X/Y 就是键帽上印 A/B/X/Y 的那颗，按哪个字母发哪个字母——任何手柄都和
// Switch 一个接法：印 A 就是游戏的 A（提示条画的是 Switch 键帽，写哪个字母按哪个字母）。纯函数，前端 dm_gamepad.m 用，宿主单测 tests/t_padmap.c 核。
//   实测（iPadOS 27 + Switch Pro Controller）：印 A 的右键走 buttonA、印 B 的下键走 buttonB——系统按键帽字母给，不看位置。
//   Xbox 手柄字母和位置本来就一致（下 A、右 B、左 X、上 Y）；PS 等键帽没字母的按系统安排：下方键 = buttonA = 确认。
//   （先前认手柄类型、按位置翻译：buttonA 当下方键，任天堂键帽再换成右 A 下 B——Switch 手柄实测给的就是按键帽字母的，这一换等于换了两次，
//     NS 手柄也 A/B、X/Y 全反。现在不认类型、不做任何翻译。）
// The four face buttons of a physical controller -> game keys: the buttonA/B/X/Y given by the system (GameController) are the buttons printed
// A/B/X/Y -- the letter pressed is the letter sent -- so every controller plays like the Switch: the printed A is the game's A (the button legend
// draws Switch glyphs; press whichever letter it shows). Pure function, used by the front end dm_gamepad.m, checked by the host unit test tests/t_padmap.c.
//   Measured (iPadOS 27 + Switch Pro Controller): the right button printed A arrives as buttonA, the bottom button printed B as buttonB -- the
//   system hands them out by the printed glyph, not by position.
//   On Xbox controllers letters and positions already agree (bottom A, right B, left X, top Y); glyphs without letters (PS etc.) follow the
//   system's arrangement: the bottom button = buttonA = confirm.
//   (The old code recognized the controller type and translated by position: buttonA taken as the bottom button, then Nintendo glyphs re-swapped
//   to right A bottom B -- a Switch controller turned out to deliver its buttons by printed letter, so that extra swap flipped A/B and X/Y even
//   on an NS pad. No type recognition and no translation now.)
#pragma once
#include <stdint.h>
#include "dm_input.h"
static inline uint64_t dm_padmap_face(int a, int b, int x, int y) {   // 四个参数 = 印 A / B / X / Y 的那颗按着没有（= 系统 buttonA/B/X/Y）| The four parameters = whether the button printed A / B / X / Y is held (= system buttonA/B/X/Y)
    return (a ? DM_BTN_A : 0) | (b ? DM_BTN_B : 0) | (x ? DM_BTN_X : 0) | (y ? DM_BTN_Y : 0);
}
