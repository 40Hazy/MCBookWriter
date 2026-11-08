package com.mcbookwriter.autobook.command;

import com.mojang.brigadier.CommandDispatcher;
import net.fabricmc.fabric.api.client.command.v2.FabricClientCommandSource;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertNotNull;

class AutoBookCommandTreeTest {
    @Test
    void registersUnifiedRunCommands() {
        CommandDispatcher<FabricClientCommandSource> dispatcher = new CommandDispatcher<>();
        AutoBookCommand.register(dispatcher);

        var root = dispatcher.getRoot().getChild("autobook");
        assertNotNull(root, "autobook root");
        for (String name : new String[] {
            "help", "plan", "add", "start", "resume", "pause", "status", "list", "jobs",
            "cancel", "stop", "remove", "retry", "ui", "config"
        }) {
            assertNotNull(root.getChild(name), name + " command");
        }
        assertNotNull(root.getChild("help").getChild("topic"), "help topic argument");
        assertNotNull(root.getChild("add").getChild("job"), "add job argument");
        assertNotNull(root.getChild("remove").getChild("job"), "remove job argument");
        assertNotNull(root.getChild("retry").getChild("job"), "retry job argument");
    }

    @Test
    void keepsLegacyQueueAliases() {
        CommandDispatcher<FabricClientCommandSource> dispatcher = new CommandDispatcher<>();
        AutoBookCommand.register(dispatcher);

        var queue = dispatcher.getRoot().getChild("autobook").getChild("queue");
        assertNotNull(queue, "queue alias");
        assertNotNull(queue.getChild("add"), "queue add");
        assertNotNull(queue.getChild("list"), "queue list");
        assertNotNull(queue.getChild("start"), "queue start");
        assertNotNull(queue.getChild("clear"), "queue clear");
    }
}
