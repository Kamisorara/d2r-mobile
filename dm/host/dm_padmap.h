// 实体手柄四个面键 → 游戏键：按键帽上印的字母对应（提示条写哪个字母就按哪个字母）。纯函数，前端 dm_gamepad.m 用，宿主单测 tests/t_padmap.c 核。
//   系统（GameController）给的四个面键是按位置定的，不看键帽上的字：buttonA 下、buttonB 右、buttonX 左、buttonY 上。
//   · 任天堂手柄（Switch Pro、Joy-Con）：键帽是 右 A、下 B、上 X、左 Y —— 与 Switch 原样一致。
//   · Xbox 手柄：键帽是 下 A、右 B、左 X、上 Y。
//   · Xbox / PS / MFi 手柄（键帽没字母或键帽 = 位置：Xbox 下 A 右 B 左 X 上 Y、PS 下 × 右 ○、MFi 同 Xbox）：按位置排（下方键 = 确认）。
//   · 认不出类型的手柄：默认按任天堂排（Switch 键帽）——提示条画的就是 Switch 键帽，认不出时照 Switch 用。
//   认类型看系统给的产品类别与厂商名两个字符串（不分大小写）：有 switch / nintendo / joy-con = 任天堂；有 xbox / dualshock / dualsense / playstation / mfi = Xbox 位置排；都没有 = 默认任天堂。
//   （Switch Pro 的厂商名是「Pro Controller」、不带这些词，要靠产品类别「Switch Pro Controller」认；所以两个串都看。类别串也认不出的手柄宁可按任天堂：本项目的提示条与默认键位都源自 Switch 版。）
// The four face buttons of a physical controller -> game keys: mapped by the letter printed on the button glyph (press whichever letter the
// button button legend shows). Pure function, used by the front end dm_gamepad.m, checked by the host unit test tests/t_padmap.c.
//   The four face buttons given by the system (GameController) are defined by position, not by the letter on the button glyph:
//   buttonA bottom, buttonB right, buttonX left, buttonY top.
//   - Nintendo controllers (Switch Pro, Joy-Con): the glyphs are right A, bottom B, top X, left Y -- identical to the Switch as is.
//   - Xbox controllers: the glyphs are bottom A, right B, left X, top Y.
//   - Xbox / PS / MFi controllers (no letters on the glyphs or glyphs = positions: Xbox bottom A right B left X top Y, PS bottom cross right
//     circle, MFi as Xbox): laid out by position (bottom button = confirm).
//   - Unrecognized controllers: default to the Nintendo layout (Switch glyphs) -- the button legend draws Switch glyphs, so an unknown pad is
//     used as a Switch pad.
//   The type is recognized by the two strings given by the system, product category and vendor name (case-insensitive): switch / nintendo /
//   joy-con = Nintendo; xbox / dualshock / dualsense / playstation / mfi = Xbox positions; neither = Nintendo by default.
//   (The vendor name of the Switch Pro is "Pro Controller", which has none of these words, so it must be recognized by the product category
//   "Switch Pro Controller"; that is why both strings are checked. A controller whose category string is also unrecognized is safer treated
//   as Nintendo: this project's button legend and default keys both come from the Switch version.)
#pragma once
#include <stdint.h>
#include <string.h>
#include <strings.h>
#include "dm_input.h"
enum { DM_PADKIND_XBOX = 0, DM_PADKIND_NINTENDO = 1 };
static inline int dm_padmap_has(const char *s, const char *w) { size_t n = strlen(w); for (; s && *s; s++) if (!strncasecmp(s, w, n)) return 1; return 0; }
static inline int dm_padmap_kind(const char *category, const char *vendor) {
    static const char *const nin[] = { "switch", "nintendo", "joy-con" };
    static const char *const pos[] = { "xbox", "dualshock", "dualsense", "playstation", "mfi" };
    for (unsigned i = 0; i < sizeof nin / sizeof *nin; i++) if (dm_padmap_has(category, nin[i]) || dm_padmap_has(vendor, nin[i])) return DM_PADKIND_NINTENDO;
    for (unsigned i = 0; i < sizeof pos / sizeof *pos; i++) if (dm_padmap_has(category, pos[i]) || dm_padmap_has(vendor, pos[i])) return DM_PADKIND_XBOX;
    return DM_PADKIND_NINTENDO;   // 认不出：默认按 Switch 键帽 | Unrecognized: default to the Switch glyphs
}
static inline uint64_t dm_padmap_face(int kind, int south, int east, int west, int north) {   // 四个参数 = 下 / 右 / 左 / 上那颗按着没有 | The four parameters = whether the bottom / right / left / top button is held
    if (kind == DM_PADKIND_NINTENDO) return (east ? DM_BTN_A : 0) | (south ? DM_BTN_B : 0) | (north ? DM_BTN_X : 0) | (west ? DM_BTN_Y : 0);
    return (south ? DM_BTN_A : 0) | (east ? DM_BTN_B : 0) | (west ? DM_BTN_X : 0) | (north ? DM_BTN_Y : 0);
}
