package com.mcbookwriter.autobook.compat;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;

/** 1.21.x：当前界面保存在 Minecraft.screen。 */
public final class ScreenCompat {
    private ScreenCompat() {
    }

    public static Screen current(Minecraft client) {
        return client.screen;
    }

    public static void set(Minecraft client, Screen screen) {
        client.setScreen(screen);
    }
}
