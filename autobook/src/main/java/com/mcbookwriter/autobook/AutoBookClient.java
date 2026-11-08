package com.mcbookwriter.autobook;

import com.mcbookwriter.autobook.command.AutoBookCommand;
import com.mcbookwriter.autobook.config.AutoBookConfig;
import com.mcbookwriter.autobook.gui.UiScreens;
import com.mcbookwriter.autobook.run.RunRunner;
import com.mcbookwriter.autobook.writer.BookWriter;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class AutoBookClient implements ClientModInitializer {
    public static final String MOD_ID = "autobook";
    public static final Logger LOG = LoggerFactory.getLogger(MOD_ID);

    @Override
    public void onInitializeClient() {
        AutoBookPaths.ensureInitialized();
        AutoBookConfig.get();
        AutoBookCommand.register();
        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            BookWriter.get().tick(client);
            RunRunner.get().tick(client);
            UiScreens.tick(client);
        });
        LOG.info("AutoBook initialized");
    }
}
