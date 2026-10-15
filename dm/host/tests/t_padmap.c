// 实体手柄面键映射（dm_padmap.h）：系统 buttonA/B/X/Y 就是键帽上印 A/B/X/Y 的那颗，按哪个字母发哪个字母。期望值按规则手写。
// Physical controller face button mapping (dm_padmap.h): the system's buttonA/B/X/Y are the buttons printed A/B/X/Y; the letter pressed is the
// letter sent. Expected values are hand-written from the rule.
#include <stdio.h>
#include "../dm_padmap.h"
static int checks, fails;
#define CHECK(c, ...) do { checks++; if (c) printf("  ✓ "); else { fails++; printf("  ✗ "); } printf(__VA_ARGS__); printf("\n"); } while (0)
int main(void) {
    CHECK(dm_padmap_face(1, 0, 0, 0) == DM_BTN_A, "印 A = A"); CHECK(dm_padmap_face(0, 1, 0, 0) == DM_BTN_B, "印 B = B");
    CHECK(dm_padmap_face(0, 0, 1, 0) == DM_BTN_X, "印 X = X"); CHECK(dm_padmap_face(0, 0, 0, 1) == DM_BTN_Y, "印 Y = Y");
    CHECK(dm_padmap_face(1, 1, 0, 0) == (DM_BTN_A | DM_BTN_B), "两颗同时按：各算各的"); CHECK(dm_padmap_face(0, 0, 0, 0) == 0, "都没按 = 0");
    printf("== %d 项，失败 %d ==\n", checks, fails);
    return fails != 0;
}
