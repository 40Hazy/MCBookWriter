package com.mcbookwriter.autobook.gui;

import com.mcbookwriter.autobook.compat.ScreenCompat;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class UiScreens {
    private static final Logger LOG = LoggerFactory.getLogger("autobook");
    private static Screen pending;

    private UiScreens() {
    }

    public static void requestConfigScreen() {
        LOG.info("AutoBook: config screen requested");
        pending = new AutoBookConfigScreen();
    }

    public static void tick(Minecraft client) {
        if (pending == null || ScreenCompat.current(client) != null) {
            return;
        }
        Screen screen = pending;
        pending = null;
        ScreenCompat.set(client, screen);
        LOG.info("AutoBook: opened config screen");
    }
}
