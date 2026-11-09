package com.mcbookwriter.autobook;

import com.mcbookwriter.autobook.command.AutoBookCommand;
import com.mcbookwriter.autobook.compat.ClientCompat;
import com.mcbookwriter.autobook.compat.KeyBindingsCompat;
import com.mcbookwriter.autobook.config.AutoBookConfig;
import com.mcbookwriter.autobook.gui.UiScreens;
import com.mcbookwriter.autobook.run.RunRunner;
import com.mcbookwriter.autobook.run.RunState;
import com.mcbookwriter.autobook.writer.BookWriter;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.Minecraft;
import net.minecraft.network.chat.Component;
import org.lwjgl.glfw.GLFW;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;

public final class AutoBookClient implements ClientModInitializer {
    public static final String MOD_ID = "autobook";
    public static final Logger LOG = LoggerFactory.getLogger(MOD_ID);

    private static KeyMapping openConfigKey;
    private static KeyMapping toggleRunKey;

    @Override
    public void onInitializeClient() {
        AutoBookPaths.ensureInitialized();
        AutoBookConfig.get();
        AutoBookCommand.register();
        openConfigKey = KeyBindingsCompat.register("key.autobook.open_config", GLFW.GLFW_KEY_F8, "key.categories.autobook");
        toggleRunKey = KeyBindingsCompat.register("key.autobook.toggle_run", GLFW.GLFW_KEY_F9, "key.categories.autobook");
        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            BookWriter.get().tick(client);
            RunRunner.get().tick(client);
            UiScreens.tick(client);
            while (openConfigKey.consumeClick()) {
                UiScreens.requestConfigScreen();
            }
            while (toggleRunKey.consumeClick()) {
                toggleRun(client);
            }
        });
        LOG.info("AutoBook initialized");
    }

    private static void toggleRun(Minecraft client) {
        RunRunner runner = RunRunner.get();
        String message;
        try {
            if (!runner.active()) {
                message = "AutoBook: 当前没有运行中的任务";
            } else if (RunState.RUN_PAUSED.equals(runner.state().status)) {
                runner.resume();
                message = "AutoBook: 已继续运行";
            } else {
                message = "AutoBook: " + runner.pause();
            }
        } catch (IOException | IllegalStateException e) {
            message = "AutoBook: " + e.getMessage();
        }
        if (client.player != null) {
            ClientCompat.actionBar(client.player, Component.literal(message));
        }
    }
}
